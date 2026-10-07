# Reuse native-generated game data and build tools. Only target code is
# cross-compiled; Rosetta is not required to produce Universal 2 on Apple Silicon.
override TARGETPFX = ../targets/$(CROSS_ARCH)/
override TARGET_CC = clang -arch $(CROSS_ARCH)
override TARGET_LINK = clang -arch $(CROSS_ARCH)
override GAMEBIN = $(TARGETPFX)nethack
override LUALIBS = $(TARGETPFX)liblua.a -lm
$(TARGETPFX)hacklib.a: $(TARGETPFX)hacklib.o
	ar rcs $@ $<
