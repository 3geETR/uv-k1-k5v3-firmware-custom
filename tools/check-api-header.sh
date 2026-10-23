#!/usr/bin/env bash
# app_api.h hızlı sentaks kontrolü (gcc, Windows'ta WSL içinden).
#
#   wsl -e bash tools/check-api-header.sh [repo-koku]
#
# Host derleyici 64-bit olduğu için _Static_assert offset kontrolleri devre dışı
# bırakılır; burada amaç yalnızca merge sonrası bozulmuş C sözdizimini
# (eksik parantez, yarım kalmış struct, çakışma artığı) yakalamaktır.
# Offset/boyut doğrulaması gerçek ARM derlemesinde (Docker/CI) yapılır.
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

cat > "$F/probe.c" <<'EOF'
#define _Static_assert(...)
#include "app_api.h"
int probe(void) { return (int)sizeof(app_api_t); }
EOF

gcc -fsyntax-only -nostdinc -I"$F" -I"$ROOT/App/apps" "$F/probe.c"
echo "OK: $ROOT/App/apps/app_api.h"
