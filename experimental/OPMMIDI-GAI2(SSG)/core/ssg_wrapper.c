#include "emu2149.h"
#include <stdint.h>

#ifdef _WIN32
#define EXPORT __declspec(dllexport)
#else
#define EXPORT __attribute__((visibility("default")))
#endif

#define PSG_CLOCK 1789772 // MSX/PC-88 标准时钟
#define OUTPUT_RATE 55930 // 统一采样率

EXPORT void* ssg_create() {
    PSG *psg = PSG_new(PSG_CLOCK, OUTPUT_RATE);
    PSG_reset(psg);
    return (void*)psg;
}

// 【核心修复】：直接调用底层的寄存器写入函数
EXPORT void ssg_write(void* handle, uint8_t reg, uint8_t data) {
    PSG_writeReg((PSG*)handle, reg, data); 
}

EXPORT void ssg_generate(void* handle, int16_t* buffer, int num_samples) {
    PSG *psg = (PSG*)handle;
    for (int i = 0; i < num_samples; i++) {
        buffer[i] = PSG_calc(psg);
    }
}

EXPORT void ssg_destroy(void* handle) {
    PSG_delete((PSG*)handle);
}