// opm_wrapper.c
#include <stdlib.h>
#include <string.h>
#include "opm.h"

#ifdef _WIN32
#define EXPORT __declspec(dllexport)
#else
#define EXPORT __attribute__((visibility("default")))
#endif

EXPORT opm_t* opm_create(uint32_t flags) {
    opm_t *chip = (opm_t*)calloc(1, sizeof(opm_t));
    if (chip) OPM_Reset(chip, flags);
    return chip;
}

EXPORT void opm_destroy(opm_t *chip) { free(chip); }

EXPORT void opm_write(opm_t *chip, uint32_t port, uint8_t data) {
    OPM_Write(chip, port, data);
    for (uint32_t i = 0; i < 64; i++) {
        OPM_Clock(chip, NULL, NULL, NULL, NULL);
    }
}

EXPORT uint8_t opm_read(opm_t *chip, uint32_t port) {
    return OPM_Read(chip, port);
}

EXPORT void opm_generate(opm_t *chip, int16_t *out, uint32_t nframes) {
    for (uint32_t i = 0; i < nframes; i++) {
        int32_t output[2] = {0};
        for (uint32_t j = 0; j < 64; j++) {
            OPM_Clock(chip, output, NULL, NULL, NULL);
        }
        
        int32_t l = output[0];
        int32_t r = output[1];
        
        // 【救命代码】在强转之前，把超过 16-bit 的波峰平滑地砍掉，防止回绕！
        if (l > 32767) l = 32767;
        if (l < -32767) l = -32767;
        if (r > 32767) r = 32767;
        if (r < -32767) r = -32767;
        
        out[i * 2]     = (int16_t)l;
        out[i * 2 + 1] = (int16_t)r;
    }
}