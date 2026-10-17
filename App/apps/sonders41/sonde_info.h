/* Common decoded radiosonde fields (RS41 app). */
#ifndef SONDE_INFO_H
#define SONDE_INFO_H
#include <stdint.h>

typedef struct {
    char id[12];
    int32_t latS, lonS, alt_m;
    uint8_t flags;
} sonde_info_t;

enum {
    SONDE_HAS_POS = 1u,
    SONDE_HAS_ALT = 2u,
    SONDE_HAS_ID  = 32u
};
#endif
