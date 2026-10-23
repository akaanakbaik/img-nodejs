#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <fcntl.h>

/* Public Brotli decoder ABI types/signatures; kept local to avoid requiring headers. */
typedef struct BrotliDecoderStateStruct BrotliDecoderState;
typedef enum { BROTLI_DECODER_ERROR = 0, BROTLI_DECODER_SUCCESS = 1, BROTLI_DECODER_NEEDS_MORE_INPUT = 2, BROTLI_DECODER_NEEDS_MORE_OUTPUT = 3 } BrotliDecoderResult;
typedef BrotliDecoderResult (*stream_fn)(BrotliDecoderState *, size_t *, const uint8_t **, size_t *, uint8_t **, size_t *);
typedef BrotliDecoderResult (*one_shot_fn)(size_t, const uint8_t *, size_t *, uint8_t *);

static stream_fn real_stream;
static one_shot_fn real_one_shot;
static int log_fd = -1;

static void probe_init(void) {
    const char *path = getenv("BROTLI_PROBE_LOG");
    if (path) log_fd = open(path, O_WRONLY | O_CREAT | O_APPEND | O_CLOEXEC, 0600);
    real_stream = (stream_fn)dlsym(RTLD_NEXT, "BrotliDecoderDecompressStream");
    real_one_shot = (one_shot_fn)dlsym(RTLD_NEXT, "BrotliDecoderDecompress");
}
__attribute__((constructor)) static void init(void) { probe_init(); }
static void mark(const char *name) {
    if (log_fd >= 0) {
        char b[128]; int n = snprintf(b, sizeof b, "BROTLI_PROBE_CALLED %s pid=%ld\n", name, (long)getpid());
        if (n > 0) (void)write(log_fd, b, (size_t)n);
    }
}
BrotliDecoderResult BrotliDecoderDecompressStream(BrotliDecoderState *s, size_t *a, const uint8_t **b, size_t *c, uint8_t **d, size_t *e) {
    mark("BrotliDecoderDecompressStream");
    if (!real_stream) real_stream = (stream_fn)dlsym(RTLD_NEXT, "BrotliDecoderDecompressStream");
    return real_stream ? real_stream(s, a, b, c, d, e) : BROTLI_DECODER_ERROR;
}
BrotliDecoderResult BrotliDecoderDecompress(size_t a, const uint8_t *b, size_t *c, uint8_t *d) {
    mark("BrotliDecoderDecompress");
    if (!real_one_shot) real_one_shot = (one_shot_fn)dlsym(RTLD_NEXT, "BrotliDecoderDecompress");
    return real_one_shot ? real_one_shot(a, b, c, d) : BROTLI_DECODER_ERROR;
}
