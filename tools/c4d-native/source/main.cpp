#include "c4d.h"
#include "c4d_graphview.h"
#include "c4d_plugin.h"
#include "c4d_resource.h"
#include <algorithm>
#include <cmath>
#include <cstring>
#include <cstdint>
#include <dlfcn.h>
#include <mach-o/dyld.h>
#include <mach-o/loader.h>

using namespace cinema;

extern "C" __attribute__((visibility("default"))) cinema::Int32 SMGvNavigate(
	cinema::Float screenX, cinema::Float screenY, cinema::Float deltaX,
	cinema::Float deltaY, cinema::Int32 phase, cinema::Int32 zoom);
extern "C" __attribute__((visibility("default"))) cinema::Int32 SMGvReady();
extern "C" __attribute__((visibility("default"))) cinema::Int32 SMGvStatus(cinema::Int32 index);
extern "C" __attribute__((visibility("default"))) std::uint64_t SMGvAddress(cinema::Int32 kind);
extern "C" __attribute__((visibility("default"))) cinema::Float SMGvMetric(cinema::Int32 kind);
extern "C" __attribute__((visibility("default"))) std::uint64_t SMTimelineAddress(cinema::Int32 kind);
extern "C" __attribute__((visibility("default"))) cinema::Int32 SMTimelineDialogVisible(std::uint64_t parent);
extern "C" __attribute__((visibility("default"))) std::uint64_t SMTimelineDialogWindow(std::uint64_t parent);
extern "C" __attribute__((visibility("default"))) cinema::Int32 SMTimelineDialogRect(
	std::uint64_t parent, cinema::Int32 id, cinema::Int32* coordinates);
extern "C" __attribute__((visibility("default"))) cinema::Int32 SMTimelineDialogSetVisible(
	std::uint64_t parent, cinema::Int32 id, cinema::Int32 x1, cinema::Int32 y1,
	cinema::Int32 x2, cinema::Int32 y2);
extern "C" __attribute__((visibility("default"))) cinema::Int32 SMTimelineAreaWidth(std::uint64_t area);
extern "C" __attribute__((visibility("default"))) cinema::Int32 SMTimelineAreaConvert(
	std::uint64_t area, cinema::Float* x, cinema::Float* y, cinema::Int32 localToScreen);
extern "C" __attribute__((visibility("default"))) void SMTimelineAreaRedraw(std::uint64_t area);

namespace
{
Bool g_ready = false;
Int32 g_status[14] = {};
GvNodeGUI* g_lastGui = nullptr;
GeUserArea* g_lastArea = nullptr;

#if defined(__aarch64__) || defined(__arm64__)
// The private routines are deliberately identified by their implementation,
// not by an image offset. This lets ASLR, relinking, and ordinary C4D rebuilds
// move them freely while still making an incompatible private ABI fail closed.
constexpr std::uint8_t kSetTranslationSignature[] = {
	0xe9, 0x23, 0xbd, 0x6d, 0xf4, 0x4f, 0x01, 0xa9,
	0xfd, 0x7b, 0x02, 0xa9, 0xfd, 0x83, 0x00, 0x91,
	0x28, 0x40, 0x60, 0x1e, 0x09, 0x40, 0x60, 0x1e,
	0xe0, 0x03, 0x02, 0xaa, 0x33, 0xa0, 0x40, 0xb9
};
constexpr std::uint8_t kGetTranslationSignature[] = {
	0xf6, 0x57, 0xbd, 0xa9, 0xf4, 0x4f, 0x01, 0xa9,
	0xfd, 0x7b, 0x02, 0xa9, 0xfd, 0x83, 0x00, 0x91,
	0xf3, 0x03, 0x04, 0xaa, 0xf4, 0x03, 0x03, 0xaa,
	0xe0, 0x03, 0x02, 0xaa, 0x35, 0xa0, 0x40, 0xb9
};
constexpr std::uint8_t kSetZoomSignature[] = {
	0xe9, 0x23, 0xbd, 0x6d, 0xf4, 0x4f, 0x01, 0xa9,
	0xfd, 0x7b, 0x02, 0xa9, 0xfd, 0x83, 0x00, 0x91,
	0xe0, 0x03, 0x02, 0xaa, 0xe8, 0xe7, 0x01, 0xb2,
	0x48, 0x33, 0x93, 0xf2, 0x28, 0xf3, 0xe7, 0xf2
};

using GetTranslation = void (*)(void*, GvNodeGUI*, GvNode*, Float*, Float*);
using SetTranslation = void (*)(void*, GvNodeGUI*, GvNode*, Float, Float);
using SetZoom = void (*)(void*, GvNodeGUI*, GvNode*, Float);

struct TextRange
{
	const std::uint8_t* begin = nullptr;
	std::size_t size = 0;
};

struct PrivateApi
{
	GetTranslation getTranslation = nullptr;
	SetTranslation setTranslation = nullptr;
	SetZoom setZoom = nullptr;
	Int32 helperType = 0;
	std::size_t helperWhenEqual = 0;
	std::size_t helperOtherwise = 0;
	Bool valid = false;
};

struct TimelinePrivateApi
{
	const std::uint8_t* range = nullptr;
	const std::uint8_t* vertical = nullptr;
	const std::uint8_t* redraw = nullptr;
	const std::uint8_t* registry = nullptr;
	Bool valid = false;
};

constexpr std::uint8_t kTimelineRangeSignature[] = {
	0xff, 0xc3, 0x02, 0xd1, 0xeb, 0x2b, 0x03, 0x6d,
	0xe9, 0x23, 0x04, 0x6d, 0xfc, 0x6f, 0x05, 0xa9,
	0xfa, 0x67, 0x06, 0xa9, 0xf8, 0x5f, 0x07, 0xa9,
	0xf6, 0x57, 0x08, 0xa9, 0xf4, 0x4f, 0x09, 0xa9,
	0xfd, 0x7b, 0x0a, 0xa9, 0xfd, 0x83, 0x02, 0x91,
	0xf8, 0x03, 0x03, 0xaa, 0xf6, 0x03, 0x02, 0xaa
};
constexpr std::uint8_t kTimelineVerticalSignature[] = {
	0xe9, 0x23, 0xbd, 0x6d, 0xf4, 0x4f, 0x01, 0xa9,
	0xfd, 0x7b, 0x02, 0xa9, 0xfd, 0x83, 0x00, 0x91,
	0x29, 0x40, 0x60, 0x1e, 0x08, 0x40, 0x60, 0x1e,
	0xf3, 0x03, 0x00, 0xaa, 0x01, 0x00, 0x80, 0x52
};
constexpr std::uint8_t kTimelineRedrawSignature[] = {
	0xff, 0x03, 0x03, 0xd1, 0xfc, 0x6f, 0x06, 0xa9,
	0xfa, 0x67, 0x07, 0xa9, 0xf8, 0x5f, 0x08, 0xa9,
	0xf6, 0x57, 0x09, 0xa9, 0xf4, 0x4f, 0x0a, 0xa9,
	0xfd, 0x7b, 0x0b, 0xa9, 0xfd, 0xc3, 0x02, 0x91,
	0x08, 0x10, 0x40, 0xf9, 0xc8, 0x25, 0x00, 0xb4,
	0xfc, 0x03, 0x07, 0xaa, 0xfb, 0x03, 0x05, 0xaa
};
constexpr std::uint8_t kTimelineRegistrySignature[] = {
	0xff, 0x03, 0x02, 0xd1, 0xe9, 0x23, 0x02, 0x6d,
	0xfa, 0x67, 0x03, 0xa9, 0xf8, 0x5f, 0x04, 0xa9,
	0xf6, 0x57, 0x05, 0xa9, 0xf4, 0x4f, 0x06, 0xa9,
	0xfd, 0x7b, 0x07, 0xa9, 0xfd, 0xc3, 0x01, 0x91
};

Bool ContainsStateKey(const std::uint8_t* begin, std::size_t size, std::uint32_t key)
{
	// MOV W1, #key. The private accessors pass their view-state key as the
	// second argument; combining this semantic marker with the ABI prologue
	// distinguishes otherwise identical generated setters.
	const std::uint32_t instruction = 0x52800001U | (key << 5);
	for (std::size_t offset = 0; offset + 4 <= size; offset += 4)
	{
		std::uint32_t candidate = 0;
		std::memcpy(&candidate, begin + offset, sizeof(candidate));
		if (candidate == instruction)
			return true;
	}
	return false;
}

const std::uint8_t* FindUniqueSignature(const TextRange& text,
	const std::uint8_t* signature, std::size_t signatureSize,
	std::uint32_t firstStateKey, std::uint32_t secondStateKey = 0)
{
	if (!text.begin || !signature || signatureSize == 0 || signatureSize > text.size)
		return nullptr;
	const std::uint8_t* match = nullptr;
	for (std::size_t offset = 0; offset + signatureSize <= text.size; offset += 4)
	{
		const std::uint8_t* candidate = text.begin + offset;
		if (std::memcmp(candidate, signature, signatureSize) != 0)
			continue;
		const std::size_t remaining = text.size - offset;
		const std::size_t inspectionSize = std::min<std::size_t>(remaining, 384);
		if (!ContainsStateKey(candidate, inspectionSize, firstStateKey) ||
			(secondStateKey && !ContainsStateKey(candidate, inspectionSize, secondStateKey)))
			continue;
		if (match)
			return nullptr;
		match = candidate;
	}
	return match;
}

const std::uint8_t* FindUniqueBytes(
	const TextRange& text, const std::uint8_t* signature, std::size_t signatureSize)
{
	if (!text.begin || !signature || signatureSize == 0 || signatureSize > text.size)
		return nullptr;
	const std::uint8_t* match = nullptr;
	for (std::size_t offset = 0; offset + signatureSize <= text.size; offset += 4)
	{
		const std::uint8_t* candidate = text.begin + offset;
		if (std::memcmp(candidate, signature, signatureSize) != 0)
			continue;
		if (match)
			return nullptr;
		match = candidate;
	}
	return match;
}

TextRange FindLoadedText(const void* address)
{
	Dl_info image = {};
	if (!address || dladdr(address, &image) == 0 || !image.dli_fbase)
		return {};
	const auto* header = reinterpret_cast<const mach_header_64*>(image.dli_fbase);
	if (header->magic != MH_MAGIC_64)
		return {};
	const std::uint8_t* commandAddress = reinterpret_cast<const std::uint8_t*>(header + 1);
	std::uint64_t textVmAddress = 0;
	const section_64* codeSection = nullptr;
	for (std::uint32_t index = 0; index < header->ncmds; ++index)
	{
		const auto* command = reinterpret_cast<const load_command*>(commandAddress);
		if (command->cmdsize < sizeof(load_command))
			return {};
		if (command->cmd == LC_SEGMENT_64)
		{
			const auto* segment = reinterpret_cast<const segment_command_64*>(command);
			if (std::strncmp(segment->segname, "__TEXT", sizeof(segment->segname)) == 0)
				textVmAddress = segment->vmaddr;
			const auto* section = reinterpret_cast<const section_64*>(segment + 1);
			for (std::uint32_t sectionIndex = 0; sectionIndex < segment->nsects; ++sectionIndex)
			{
				if (std::strncmp(section[sectionIndex].segname, "__TEXT", sizeof(section[sectionIndex].segname)) == 0 &&
					std::strncmp(section[sectionIndex].sectname, "__text", sizeof(section[sectionIndex].sectname)) == 0)
					codeSection = &section[sectionIndex];
			}
		}
		commandAddress += command->cmdsize;
	}
	if (!codeSection || codeSection->size == 0)
		return {};
	const auto* imageBase = reinterpret_cast<const std::uint8_t*>(image.dli_fbase);
	return { imageBase + (codeSection->addr - textVmAddress), std::size_t(codeSection->size) };
}

TextRange FindImageText(const char* suffix)
{
	if (!suffix)
		return {};
	const std::size_t suffixLength = std::strlen(suffix);
	for (std::uint32_t index = 0; index < _dyld_image_count(); ++index)
	{
		const char* name = _dyld_get_image_name(index);
		if (!name)
			continue;
		const std::size_t nameLength = std::strlen(name);
		if (nameLength < suffixLength || std::strcmp(name + nameLength - suffixLength, suffix) != 0)
			continue;
		const auto* rawHeader = _dyld_get_image_header(index);
		const auto* header = reinterpret_cast<const mach_header_64*>(rawHeader);
		if (!header || header->magic != MH_MAGIC_64)
			return {};
		Dl_info image = {};
		if (dladdr(header, &image) == 0 || !image.dli_fbase)
			return {};
		const std::uint8_t* commandAddress = reinterpret_cast<const std::uint8_t*>(header + 1);
		std::uint64_t textVmAddress = 0;
		const section_64* codeSection = nullptr;
		for (std::uint32_t commandIndex = 0; commandIndex < header->ncmds; ++commandIndex)
		{
			const auto* command = reinterpret_cast<const load_command*>(commandAddress);
			if (command->cmdsize < sizeof(load_command))
				return {};
			if (command->cmd == LC_SEGMENT_64)
			{
				const auto* segment = reinterpret_cast<const segment_command_64*>(command);
				if (std::strncmp(segment->segname, "__TEXT", sizeof(segment->segname)) == 0)
					textVmAddress = segment->vmaddr;
				const auto* section = reinterpret_cast<const section_64*>(segment + 1);
				for (std::uint32_t sectionIndex = 0; sectionIndex < segment->nsects; ++sectionIndex)
				{
					if (std::strncmp(section[sectionIndex].segname, "__TEXT", sizeof(section[sectionIndex].segname)) == 0 &&
						std::strncmp(section[sectionIndex].sectname, "__text", sizeof(section[sectionIndex].sectname)) == 0)
						codeSection = &section[sectionIndex];
				}
			}
			commandAddress += command->cmdsize;
		}
		if (!codeSection || codeSection->size == 0)
			return {};
		const auto* imageBase = reinterpret_cast<const std::uint8_t*>(image.dli_fbase);
		return { imageBase + (codeSection->addr - textVmAddress), std::size_t(codeSection->size) };
	}
	return {};
}

std::uint32_t ReadInstruction(const std::uint8_t* address)
{
	std::uint32_t instruction = 0;
	std::memcpy(&instruction, address, sizeof(instruction));
	return instruction;
}

const std::uint8_t* FollowArm64Branch(const std::uint8_t* address, const TextRange& text)
{
	const std::uint32_t instruction = ReadInstruction(address);
	if ((instruction & 0xfc000000U) != 0x14000000U)
		return address;
	std::int64_t displacement = std::int64_t(instruction & 0x03ffffffU);
	if (displacement & 0x02000000)
		displacement |= ~std::int64_t(0x03ffffffU);
	const std::uint8_t* target = address + displacement * 4;
	return target >= text.begin && target < text.begin + text.size ? target : nullptr;
}

Bool DecodeMovWide(std::uint32_t instruction, std::uint32_t opcode,
	std::uint32_t& reg, std::uint32_t& value, std::uint32_t& shift)
{
	if ((instruction & 0x7f800000U) != opcode)
		return false;
	reg = instruction & 31U;
	value = (instruction >> 5) & 0xffffU;
	shift = ((instruction >> 21) & 3U) * 16U;
	return shift <= 16;
}

Bool ResolveHelperLayout(const std::uint8_t* publicGetZoom, const TextRange& text,
	Int32& helperType, std::size_t& helperWhenEqual, std::size_t& helperOtherwise)
{
	const std::uint8_t* implementation = FollowArm64Branch(publicGetZoom, text);
	if (!implementation)
		return false;
	// The public implementation asks the root for its type, builds that type ID,
	// selects one of two helper fields, and loads the selected field. Decode that
	// decision instead of assuming either the type ID or object layout.
	for (std::size_t index = 0; index + 4 < 48; ++index)
	{
		const std::uint32_t movTypeLow = ReadInstruction(implementation + index * 4);
		const std::uint32_t movTypeHigh = ReadInstruction(implementation + (index + 1) * 4);
		const std::uint32_t movOtherwise = ReadInstruction(implementation + (index + 2) * 4);
		const std::uint32_t movEqual = ReadInstruction(implementation + (index + 3) * 4);
		std::uint32_t typeReg = 0, typeLow = 0, typeLowShift = 0;
		std::uint32_t typeHighReg = 0, typeHigh = 0, typeHighShift = 0;
		std::uint32_t otherwiseReg = 0, otherwise = 0, otherwiseShift = 0;
		std::uint32_t equalReg = 0, equal = 0, equalShift = 0;
		if (!DecodeMovWide(movTypeLow, 0x52800000U, typeReg, typeLow, typeLowShift) || typeLowShift != 0 ||
			!DecodeMovWide(movTypeHigh, 0x72800000U, typeHighReg, typeHigh, typeHighShift) ||
			typeHighReg != typeReg || typeHighShift != 16 ||
			!DecodeMovWide(movOtherwise, 0x52800000U, otherwiseReg, otherwise, otherwiseShift) || otherwiseShift != 0 ||
			!DecodeMovWide(movEqual, 0x52800000U, equalReg, equal, equalShift) || equalShift != 0)
			continue;
		if (otherwise < 0x20 || otherwise > 0x400 || equal < 0x20 || equal > 0x400 ||
			(otherwise & 7U) != 0 || (equal & 7U) != 0 || otherwise == equal)
			continue;
		const std::uint32_t expectedCompare = 0x6b00001fU | (typeReg << 16);
		Bool foundDecision = false;
		for (std::size_t decision = index + 4; decision < std::min<std::size_t>(index + 20, 48); ++decision)
		{
			if (ReadInstruction(implementation + decision * 4) != expectedCompare)
				continue;
			const std::uint32_t select = ReadInstruction(implementation + (decision + 1) * 4);
			if ((select & 0xffe00c00U) != 0x9a800000U || ((select >> 12) & 15U) != 0 ||
				((select >> 5) & 31U) != equalReg || ((select >> 16) & 31U) != otherwiseReg)
				continue;
			foundDecision = true;
			break;
		}
		if (!foundDecision)
			continue;
		helperType = Int32(typeLow | (typeHigh << 16));
		helperWhenEqual = equal;
		helperOtherwise = otherwise;
		return true;
	}
	return false;
}

Bool DecodeAdrp(const std::uint8_t* address, std::uint32_t instruction,
	std::uint32_t& reg, std::uintptr_t& value)
{
	if ((instruction & 0x9f000000U) != 0x90000000U)
		return false;
	reg = instruction & 31U;
	std::int64_t immediate = std::int64_t(((instruction >> 5) & 0x7ffffU) << 2) |
		std::int64_t((instruction >> 29) & 3U);
	if (immediate & (std::int64_t(1) << 20))
		immediate |= ~((std::int64_t(1) << 21) - 1);
	value = (reinterpret_cast<std::uintptr_t>(address) & ~std::uintptr_t(0xfff)) +
		std::uintptr_t(immediate << 12);
	return true;
}

const std::uint8_t* ResolveTimelineRegistryCandidate(
	const std::uint8_t* candidate, std::size_t availableBytes)
{
	std::uintptr_t registers[32] = {};
	std::uintptr_t stores[32] = {};
	std::size_t storeCount = 0;
	const std::size_t instructionCount = std::min<std::size_t>(64, availableBytes / 4);
	for (std::size_t index = 0; index < instructionCount; ++index)
	{
		const std::uint8_t* address = candidate + index * 4;
		const std::uint32_t instruction = ReadInstruction(address);
		std::uint32_t reg = 0;
		std::uintptr_t value = 0;
		if (DecodeAdrp(address, instruction, reg, value))
		{
			registers[reg] = value;
			continue;
		}
		if ((instruction & 0xff000000U) == 0x91000000U)
		{
			const std::uint32_t destination = instruction & 31U;
			const std::uint32_t source = (instruction >> 5) & 31U;
			std::uintptr_t immediate = (instruction >> 10) & 0xfffU;
			if (instruction & (1U << 22))
				immediate <<= 12;
			if (registers[source])
				registers[destination] = registers[source] + immediate;
			continue;
		}
		if ((instruction & 0xffc00000U) == 0xf9000000U && (instruction & 31U) == 0)
		{
			const std::uint32_t baseReg = (instruction >> 5) & 31U;
			if (registers[baseReg] && storeCount < 32)
				stores[storeCount++] = registers[baseReg] + std::uintptr_t((instruction >> 10) & 0xfffU) * 8;
		}
	}
	for (std::size_t index = 0; index < storeCount; ++index)
	{
		const std::uintptr_t first = stores[index];
		Bool found[4] = { false, false, false, false };
		for (std::size_t other = 0; other < storeCount; ++other)
		{
			for (std::size_t slot = 0; slot < 4; ++slot)
				if (stores[other] == first + slot * 8)
					found[slot] = true;
		}
		if (found[0] && found[1] && found[2] && found[3])
			return reinterpret_cast<const std::uint8_t*>(first);
	}
	return nullptr;
}

const std::uint8_t* FindTimelineRegistry(const TextRange& text)
{
	const std::uint8_t* registry = nullptr;
	for (std::size_t offset = 0; offset + sizeof(kTimelineRegistrySignature) <= text.size; offset += 4)
	{
		const std::uint8_t* candidate = text.begin + offset;
		if (std::memcmp(candidate, kTimelineRegistrySignature, sizeof(kTimelineRegistrySignature)) != 0)
			continue;
		const std::uint8_t* resolved = ResolveTimelineRegistryCandidate(candidate, text.size - offset);
		if (!resolved)
			continue;
		if (registry && registry != resolved)
			return nullptr;
		registry = resolved;
	}
	return registry;
}

TimelinePrivateApi ResolveTimelinePrivateApi()
{
	TimelinePrivateApi api;
	const TextRange text = FindImageText("/c4d_manager.xlib");
	if (!text.begin)
		return api;
	api.range = FindUniqueBytes(text, kTimelineRangeSignature, sizeof(kTimelineRangeSignature));
	api.vertical = FindUniqueBytes(text, kTimelineVerticalSignature, sizeof(kTimelineVerticalSignature));
	api.redraw = FindUniqueBytes(text, kTimelineRedrawSignature, sizeof(kTimelineRedrawSignature));
	api.registry = FindTimelineRegistry(text);
	api.valid = api.range && api.vertical && api.redraw && api.registry;
	return api;
}

const TimelinePrivateApi& GetTimelinePrivateApi()
{
	static const TimelinePrivateApi api = ResolveTimelinePrivateApi();
	return api;
}

PrivateApi ResolvePrivateApi()
{
	PrivateApi api;
	const auto* publicGetZoom = reinterpret_cast<const std::uint8_t*>(C4DOS_Gv->gui->GuiGetZoom);
	const TextRange text = FindLoadedText(publicGetZoom);
	if (!text.begin)
		return api;
	const std::uint8_t* setTranslation = FindUniqueSignature(
		text, kSetTranslationSignature, sizeof(kSetTranslationSignature), 0x66, 0x67);
	const std::uint8_t* getTranslation = FindUniqueSignature(
		text, kGetTranslationSignature, sizeof(kGetTranslationSignature), 0x66, 0x67);
	const std::uint8_t* setZoom = FindUniqueSignature(
		text, kSetZoomSignature, sizeof(kSetZoomSignature), 0x68);
	if (!setTranslation || !getTranslation || !setZoom ||
		!ResolveHelperLayout(publicGetZoom, text, api.helperType, api.helperWhenEqual, api.helperOtherwise))
		return api;
	api.setTranslation = reinterpret_cast<SetTranslation>(const_cast<std::uint8_t*>(setTranslation));
	api.getTranslation = reinterpret_cast<GetTranslation>(const_cast<std::uint8_t*>(getTranslation));
	api.setZoom = reinterpret_cast<SetZoom>(const_cast<std::uint8_t*>(setZoom));
	api.valid = true;
	return api;
}

const PrivateApi& GetPrivateApi()
{
	static const PrivateApi api = ResolvePrivateApi();
	return api;
}

void* ResolveHelper(GvNodeGUI* gui, GvNode* root, const PrivateApi& api)
{
	if (!gui || !root || !api.valid)
		return nullptr;
	const std::size_t offset = root->GetType() == api.helperType ? api.helperWhenEqual : api.helperOtherwise;
	return *reinterpret_cast<void**>(reinterpret_cast<std::uint8_t*>(gui) + offset);
}

Bool DirectPan(GvNodeGUI* gui, Float deltaX, Float deltaY)
{
	if (!gui || !std::isfinite(deltaX) || !std::isfinite(deltaY))
		return false;
	GvNodeMaster* master = gui->GetMaster();
	GvNode* root = master ? master->GetRoot() : nullptr;
	if (!root)
		return false;

	const PrivateApi& api = GetPrivateApi();
	if (!api.valid)
		return false;
	void* helper = ResolveHelper(gui, root, api);
	if (!helper)
		return false;
	Float x = 0.0;
	Float y = 0.0;
	api.getTranslation(helper, gui, root, &x, &y);
	if (!std::isfinite(x) || !std::isfinite(y))
		return false;
	Float zoom = 1.0;
	gui->GetZoom(root, zoom);
	if (!std::isfinite(zoom) || zoom <= 0.0)
		return false;
	// The private translation is stored in graph units, while the Node Editor
	// scroll path consumes screen-pixel deltas. Convert pixels to graph units so
	// visible pan speed remains continuous and independent of the current zoom.
	api.setTranslation(helper, gui, root, x + deltaX / zoom, y + deltaY / zoom);
	gui->Redraw();
	return true;
}

Bool DirectZoom(GvNodeGUI* gui, Float delta)
{
	if (!gui || !std::isfinite(delta))
		return false;
	GvNodeMaster* master = gui->GetMaster();
	GvNode* root = master ? master->GetRoot() : nullptr;
	if (!root)
		return false;

	const PrivateApi& api = GetPrivateApi();
	if (!api.valid)
		return false;
	void* helper = ResolveHelper(gui, root, api);
	if (!helper)
		return false;

	Float zoom = 1.0;
	gui->GetZoom(root, zoom);
	if (!std::isfinite(zoom) || zoom <= 0.0)
		return false;
	// Match node_event_transport.py: equal positive/negative input produces
	// reciprocal zoom factors while retaining the infinitesimal 0.002 gain.
	const Float amount = std::min(std::abs(delta) * 0.002, 0.95);
	const Float factor = delta > 0.0 ? 1.0 / (1.0 - amount) : 1.0 - amount;
	const Float target = std::max(0.025, std::min(64.0, zoom * factor));
	api.setZoom(helper, gui, root, target);
	gui->Redraw();
	return true;
}
#else
Bool DirectPan(GvNodeGUI*, Float, Float)
{
	return false;
}
Bool DirectZoom(GvNodeGUI*, Float)
{
	return false;
}
#endif

GvNodeGUI* FindHoveredGui(BaseDocument* document, Float screenX, Float screenY)
{
	for (Int32 index = 2; index < 14; ++index)
		g_status[index] = 0;
	if (!document)
		return nullptr;
	g_status[2] = 1;

	auto inspectTags = [screenX, screenY](BaseObject* object) -> GvNodeGUI*
	{
		for (BaseTag* tag = object->GetFirstTag(); tag; tag = tag->GetNext())
		{
			if (!tag->IsInstanceOf(Texpresso))
				continue;
			++g_status[3];
			GvNodeMaster* master = static_cast<XPressoTag*>(tag)->GetNodeMaster();
			if (!master)
				continue;
			++g_status[4];
			for (UInt32 index = 0; index < 32; ++index)
			{
				GvNodeGUI* gui = GvGetWorld()->GetMasterGUI(master, index);
				if (!gui)
					break;
				++g_status[5];
				GeUserArea* area = gui->GetUserArea();
				if (!area || area->GetWidth() < 100 || area->GetHeight() < 60)
					continue;
				++g_status[6];
				Float x = screenX;
				Float y = screenY;
				g_status[8] = area->GetWidth();
				g_status[9] = area->GetHeight();
				if (area->Screen2Local(x, y) && x >= 0.0 && y >= 0.0 &&
					x < Float(area->GetWidth()) && y < Float(area->GetHeight()))
				{
					g_status[7] = 1;
					g_status[10] = Int32(x);
					g_status[11] = Int32(y);
					g_lastGui = gui;
					g_lastArea = area;
					return gui;
				}
			}
		}
		return nullptr;
	};

	for (BaseObject* root = document->GetFirstObject(); root; root = root->GetNext())
	{
		for (BaseObject* object = root; object;)
		{
			if (GvNodeGUI* gui = inspectTags(object))
				return gui;
			if (object->GetDown())
			{
				object = object->GetDown();
				continue;
			}
			while (object && object != root && !object->GetNext())
				object = object->GetUp();
			object = object ? object->GetNext() : nullptr;
		}
	}
	return nullptr;
}

extern "C" __attribute__((visibility("default"))) std::uint64_t SMGvAddress(Int32 kind)
{
	if (kind == 0)
		return reinterpret_cast<std::uintptr_t>(g_lastGui);
	if (kind == 1)
		return reinterpret_cast<std::uintptr_t>(g_lastArea);
	if (!g_lastGui)
		return 0;
	if (kind == 2)
		return reinterpret_cast<std::uintptr_t>(g_lastGui->GetMaster());
	if (kind == 3)
	{
		GvNodeMaster* master = g_lastGui->GetMaster();
		return reinterpret_cast<std::uintptr_t>(master ? master->GetRoot() : nullptr);
	}
	if (kind == 4)
		return reinterpret_cast<std::uintptr_t>(g_lastGui->GetDialog());
	if (kind == 5)
		return reinterpret_cast<std::uintptr_t>(C4DOS_Gv->gui->GuiGetZoom);
	if (kind == 6)
		return reinterpret_cast<std::uintptr_t>(C4DOS_Gv->gui->GuiMouseDown);
	if (kind == 7)
		return reinterpret_cast<std::uintptr_t>(C4DOS_Gv->gui->GuiMessage);
	if (kind == 8)
		return reinterpret_cast<std::uintptr_t>(C4DOS_Gv->gui->GuiCenterNodes);
	return 0;
}
}

extern "C" __attribute__((visibility("default"))) Float SMGvMetric(Int32 kind)
{
	if (kind != 0 || !g_lastGui)
		return 0.0;
	GvNodeMaster* master = g_lastGui->GetMaster();
	GvNode* root = master ? master->GetRoot() : nullptr;
	if (!root)
		return 0.0;
	Float zoom = 1.0;
	g_lastGui->GetZoom(root, zoom);
	return zoom;
}

extern "C" __attribute__((visibility("default"))) std::uint64_t SMTimelineAddress(Int32 kind)
{
	if (kind == 0)
		return reinterpret_cast<std::uintptr_t>(GetActiveDocument());
	if (kind == 1)
		return reinterpret_cast<std::uintptr_t>(C4DOS_Cd);
	if (kind == 2)
		return reinterpret_cast<std::uintptr_t>(C4DOS_Cu);
	if (kind == 3)
		return reinterpret_cast<std::uintptr_t>(C4DOS_Ln);
	if (kind == 4)
		return reinterpret_cast<std::uintptr_t>(C4DOS_At);
	if (kind == 5)
		return reinterpret_cast<std::uintptr_t>(C4DOS_Bl);
#if defined(__aarch64__) || defined(__arm64__)
	const TimelinePrivateApi& api = GetTimelinePrivateApi();
	if (!api.valid)
		return 0;
	if (kind == 6)
		return reinterpret_cast<std::uintptr_t>(api.range);
	if (kind == 7)
		return reinterpret_cast<std::uintptr_t>(api.vertical);
	if (kind == 8)
		return reinterpret_cast<std::uintptr_t>(api.redraw);
	if (kind == 9)
		return reinterpret_cast<std::uintptr_t>(api.registry);
#endif
	return 0;
}

extern "C" __attribute__((visibility("default"))) Int32 SMTimelineDialogVisible(std::uint64_t parent)
{
	auto* dialog = reinterpret_cast<GeDialog*>(std::uintptr_t(parent));
	return dialog && dialog->IsVisible() ? 1 : 0;
}

extern "C" __attribute__((visibility("default"))) std::uint64_t SMTimelineDialogWindow(std::uint64_t parent)
{
	auto* dialog = reinterpret_cast<GeDialog*>(std::uintptr_t(parent));
	return reinterpret_cast<std::uintptr_t>(dialog ? dialog->GetWindowHandle() : nullptr);
}

extern "C" __attribute__((visibility("default"))) Int32 SMTimelineDialogRect(
	std::uint64_t parent, Int32 id, Int32* coordinates)
{
	auto* dialog = reinterpret_cast<GeDialog*>(std::uintptr_t(parent));
	if (!dialog || !coordinates)
		return 0;
	// Navigation must advance from the current scroll position. GetItemDim()
	// returns the control's fixed x/y/width/height and would restart every
	// packet from the same origin; GetVisibleArea() returns live x1/y1/x2/y2.
	return dialog->GetVisibleArea(id, &coordinates[0], &coordinates[1],
		&coordinates[2], &coordinates[3]) ? 1 : 0;
}

extern "C" __attribute__((visibility("default"))) Int32 SMTimelineDialogSetVisible(
	std::uint64_t parent, Int32 id, Int32 x1, Int32 y1, Int32 x2, Int32 y2)
{
	auto* dialog = reinterpret_cast<GeDialog*>(std::uintptr_t(parent));
	return dialog && dialog->SetVisibleArea(id, x1, y1, x2, y2) ? 1 : 0;
}

extern "C" __attribute__((visibility("default"))) Int32 SMTimelineAreaWidth(std::uint64_t area)
{
	auto* userArea = reinterpret_cast<GeUserArea*>(std::uintptr_t(area));
	return userArea ? userArea->GetWidth() : 0;
}

extern "C" __attribute__((visibility("default"))) Int32 SMTimelineAreaConvert(
	std::uint64_t area, Float* x, Float* y, Int32 localToScreen)
{
	auto* userArea = reinterpret_cast<GeUserArea*>(std::uintptr_t(area));
	if (!userArea || !x || !y)
		return 0;
	return (localToScreen ? userArea->Local2Screen(*x, *y) : userArea->Screen2Local(*x, *y)) ? 1 : 0;
}

extern "C" __attribute__((visibility("default"))) void SMTimelineAreaRedraw(std::uint64_t area)
{
	auto* userArea = reinterpret_cast<GeUserArea*>(std::uintptr_t(area));
	if (userArea)
		userArea->Redraw(true);
}

extern "C" __attribute__((visibility("default"))) Int32 SMGvReady()
{
	return g_ready ? 1 : 0;
}

extern "C" __attribute__((visibility("default"))) Int32 SMGvStatus(Int32 index)
{
	return index >= 0 && index < 14 ? g_status[index] : -1;
}

extern "C" __attribute__((visibility("default"))) Int32 SMGvNavigate(
	Float screenX, Float screenY, Float deltaX, Float deltaY, Int32 phase, Int32 zoom)
{
	++g_status[1];
	g_status[0] = -1;
	GvNodeGUI* gui = FindHoveredGui(GetActiveDocument(), screenX, screenY);
	if (!gui)
		return 0;

	GeUserArea* area = gui->GetUserArea();
	Float localX = screenX;
	Float localY = screenY;
	if (!area || !area->Screen2Local(localX, localY))
		return 0;
	Float globalX = localX;
	Float globalY = localY;
	if (!area->Local2Global(globalX, globalY))
		return 0;
	g_status[12] = Int32(globalX);
	g_status[13] = Int32(globalY);

	// Wheel/magnify delivery was a rejected experiment. Pan and zoom legacy
	// XPresso by changing its guarded native view state directly.
	if (!zoom && (phase == 1 || phase == 2) && (deltaX != 0.0 || deltaY != 0.0))
	{
		if (!DirectPan(gui, deltaX, deltaY))
		{
			g_status[0] = -2;
			return 1;
		}
		g_status[0] = 2;
		return 1;
	}
	if (zoom && (phase == 1 || phase == 2) && deltaY != 0.0)
	{
		if (!DirectZoom(gui, deltaY))
		{
			g_status[0] = -3;
			return 1;
		}
		g_status[0] = 3;
		return 1;
	}
	g_status[0] = 0;
	return 1;
}

cinema::Bool cinema::PluginStart()
{
	return true;
}

void cinema::PluginEnd()
{
	g_ready = false;
}

cinema::Bool cinema::PluginMessage(cinema::Int32 id, void* data)
{
	if (id == C4DPL_INIT_SYS)
	{
		g_ready = g_resource.Init();
		return g_ready;
	}
	return false;
}
