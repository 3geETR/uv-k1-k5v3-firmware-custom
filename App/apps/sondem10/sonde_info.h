/* Decoded fields used by the Sonde M10 overlay. */
#ifndef SONDE_INFO_H
#define SONDE_INFO_H
#include <stdint.h>

typedef struct {
    char     id[12];
    int32_t  latS, lonS, alt_m;
    uint16_t tRaw;      /* thermistor ADC incl. range bits */
    int16_t  temp_c10;
    int16_t  vs_dm;     /* vertical speed, dm/s (with SONDE_HAS_VEL)         */
    uint16_t hs_dm;     /* horizontal speed, dm/s (with SONDE_HAS_VEL)       */
    uint16_t hdg;       /* heading, degrees 0..359 from north (SONDE_HAS_VEL) */
    uint8_t  flags;
} sonde_info_t;

enum {
    SONDE_HAS_POS  = 1u,
    SONDE_HAS_ALT  = 2u,
    SONDE_HAS_ID   = 4u,
    SONDE_HAS_TEMP = 8u,
    SONDE_HAS_VEL  = 16u
};
#endif
