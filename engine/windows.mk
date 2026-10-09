# Atlas for NetHack: Windows engine with the shim JSON window port.
# Read after upstream sys/windows/GNUmakefile, which still builds the
# generators, game data, static Lua and recover.exe. Only the game link
# differs: the Atlas port replaces the Win32 console tty port, with the same
# build choices as the macOS hint and no upstream file changes.
ATLASDEF = -O2 -DSHIM_GRAPHICS -DNOTTYGRAPHICS -DTILES_IN_GLYPHMAP \
	-DDEFAULT_WINDOW_SYS=\"shim\" -DNOMAIL -DNOSHELL
# windconf.h includes <process.h> (for _spawnv) only under MSVC.
CFLAGSA = $(CFLAGSU) $(ATLASDEF) -include process.h
OA = $(O)atlas
ATLASOBJS = $(addprefix $(OA)/, $(COREOBJS) winshim.o tile.o)
ATLASGAME = $(GAMEDIR)/nethack.exe
# Upstream names $(DLB) before NHV is set; dlb.exe itself appends 500.
ATLASDLB = $(GAMEDIR)/nhdat500

atlas: $(ATLASGAME) $(RTARGETS) $(ATLASDLB)

$(ATLASDLB): $(U)dlb.exe $(DLBLST) | $(GAMEDIR)
	$(U)dlb.exe CcIf $(dir $(DLBLST)) $(notdir $(DLBLST)) $(SRC)/nhdat
	mv $(SRC)/nhdat500 $@

$(ATLASGAME): $(ATLASOBJS) $(OA)/date.o $(LUASTATIC) $(HLHACKLIB) | $(GAMEDIR)
	$(ld) $(LDFLAGS) -mconsole $^ $(LIBS) -static -lc++ -o$@

# As upstream: date.c is rebuilt after any other object changes.
$(OA)/date.o: $(SRC)/date.c $(ATLASOBJS) | $(OA)
	$(cc) $(CFLAGSA) $< -o$@

$(OA)/cppregex.o: $(SSYS)/cppregex.cpp $(NHLUAH) | $(OA)
	$(cxx) $(CFLAGSA) $< -o$@

$(OA)/%.o: $(SRC)/%.c $(NHLUAH) | $(OA)
	$(cc) $(CFLAGSA) $< -o$@

$(OA)/%.o: $(SSYS)/%.c $(NHLUAH) | $(OA)
	$(cc) $(CFLAGSA) $< -o$@

$(OA)/%.o: $(MSWSYS)/%.c $(NHLUAH) | $(OA)
	$(cc) $(CFLAGSA) $< -o$@

$(OA)/%.o: ../sound/windsound/%.c $(NHLUAH) | $(OA)
	$(cc) $(CFLAGSA) $< -o$@

$(OA)/%.o: ../win/shim/%.c $(NHLUAH) | $(OA)
	$(cc) $(CFLAGSA) $< -o$@

$(OA):
	@mkdir -p $@

.PHONY: atlas
