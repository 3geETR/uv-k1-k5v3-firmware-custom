#!/usr/bin/env bash
# app_api.h doğrulama (gcc, Windows'ta WSL içinden).
#
#   wsl -e bash tools/check-api-header.sh [repo-koku]
#
# 1) Derleyici -m32 destekliyorsa gerçek 32-bit yerleşimle derler: bu durumda
#    app_api.h içindeki _Static_assert offset/boyut kontrolleri de çalışır.
# 2) -m32 desteklenmiyorsa yalnızca sentaks kontrolü yapar ve uyarır; offset
#    doğrulaması için gerçek ARM derlemesi (Docker/CI) gerekir.
set -euo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=${1:-$(cd "$HERE/.." && pwd)}   # tools/ -> repo kökü
F=$(mktemp -d)
trap 'rm -rf "$F"' EXIT

cat > "$F/stdint.h" <<'EOF'
#ifndef F_STDINT
#define F_STDINT
typedef signed char int8_t;
typedef unsigned char uint8_t;
typedef short int16_t;
typedef unsigned short uint16_t;
typedef int int32_t;
typedef unsigned int uint32_t;
typedef long long int64_t;
typedef unsigned long long uint64_t;
#endif
EOF

cat > "$F/stdbool.h" <<'EOF'
#ifndef F_STDBOOL
#define F_STDBOOL
#define bool _Bool
#define true 1
#define false 0
#endif
EOF

cat > "$F/stddef.h" <<'EOF'
#ifndef F_STDDEF
#define F_STDDEF
typedef unsigned long size_t;
#define offsetof(t,m) __builtin_offsetof(t,m)
#endif
EOF

# Gerçek assert'lerle probe: 32-bit hedefte offsetler ve boyut doğrulanır.
cat > "$F/probe.c" <<'EOF'
#include "app_api.h"
int probe(void) { return (int)sizeof(app_api_t); }
EOF

if gcc -m32 -fsyntax-only -nostdinc -I"$F" -I"$ROOT/App/apps" "$F/probe.c" 2>"$F/err32"; then
    echo "OK (32-bit): $ROOT/App/apps/app_api.h - offset/boyut assertleri gecti"
    exit 0
fi

if grep -qi "assertion failed" "$F/err32"; then
    echo "HATA: app_api.h offset/boyut asserti basarisiz:" >&2
    cat "$F/err32" >&2
    exit 1
fi

# -m32 bu ortamda yok: sentaks kontrolüne düş (assertler kapatılır).
cat > "$F/probe.c" <<'EOF'
#define _Static_assert(...)
#include "app_api.h"
int probe(void) { return (int)sizeof(app_api_t); }
EOF

gcc -fsyntax-only -nostdinc -I"$F" -I"$ROOT/App/apps" "$F/probe.c"
echo "OK (syntax only): $ROOT/App/apps/app_api.h"
echo "UYARI: bu ortamda -m32 yok; offset/boyut assertleri dogrulanmadi." >&2
