/* Freeze the only uncontrolled native entropy source for capture on/off
 * comparisons. Production randomness is untouched: this shim is loaded with
 * LD_PRELOAD for both runs, so both processes see the same fixed stream.
 *
 * Installed Wesnoth 1.18.8 seeds randomness::rng::default_instance() from
 * boost::random_device, whose Linux backend opens /dev/urandom and calls
 * __read_chk (verified: nm -D libboost_random.so.1.83.0 shows open and
 * __read_chk, and strings shows /dev/urandom). --rng-seed only seeds srand.
 */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <errno.h>
#include <fcntl.h>
#include <stdarg.h>
#include <stdint.h>
#include <string.h>
#include <unistd.h>

#define MAX_TRACKED 4096

static uint64_t rng_state = 0x2545f4914f6cdd1dULL;
static unsigned char tracked[MAX_TRACKED];

static void fill_bytes(unsigned char *buffer, size_t length) {
    for (size_t i = 0; i < length; ++i) {
        rng_state ^= rng_state << 13;
        rng_state ^= rng_state >> 7;
        rng_state ^= rng_state << 17;
        buffer[i] = (unsigned char)(rng_state >> 29);
    }
}

static int is_entropy_path(const char *path) {
    if (!path) return 0;
    return strstr(path, "/dev/urandom") != NULL || strstr(path, "/dev/random") != NULL;
}

static int track(int fd) {
    if (fd >= 0 && fd < MAX_TRACKED) tracked[fd] = 1;
    return fd;
}

typedef int (*open_fn)(const char *, int, ...);
typedef int (*close_fn)(int);
typedef ssize_t (*read_fn)(int, void *, size_t);

int open(const char *path, int flags, ...) {
    static open_fn real_open;
    if (!real_open) real_open = (open_fn)dlsym(RTLD_NEXT, "open");
    mode_t mode = 0;
    if (flags & O_CREAT) {
        va_list args;
        va_start(args, flags);
        mode = (mode_t)va_arg(args, int);
        va_end(args);
    }
    int fd = real_open(path, flags, mode);
    if (is_entropy_path(path)) track(fd);
    return fd;
}

int open64(const char *path, int flags, ...) {
    static open_fn real_open64;
    if (!real_open64) real_open64 = (open_fn)dlsym(RTLD_NEXT, "open64");
    mode_t mode = 0;
    if (flags & O_CREAT) {
        va_list args;
        va_start(args, flags);
        mode = (mode_t)va_arg(args, int);
        va_end(args);
    }
    int fd = real_open64(path, flags, mode);
    if (is_entropy_path(path)) track(fd);
    return fd;
}

ssize_t read(int fd, void *buffer, size_t length) {
    static read_fn real_read;
    if (!real_read) real_read = (read_fn)dlsym(RTLD_NEXT, "read");
    if (fd >= 0 && fd < MAX_TRACKED && tracked[fd]) {
        fill_bytes((unsigned char *)buffer, length);
        return (ssize_t)length;
    }
    return real_read(fd, buffer, length);
}

ssize_t __read_chk(int fd, void *buffer, size_t length, size_t buffer_length) {
    (void)buffer_length;
    return read(fd, buffer, length);
}

int close(int fd) {
    static close_fn real_close;
    if (!real_close) real_close = (close_fn)dlsym(RTLD_NEXT, "close");
    if (fd >= 0 && fd < MAX_TRACKED) tracked[fd] = 0;
    return real_close(fd);
}

ssize_t getrandom(void *buffer, size_t length, unsigned int flags) {
    (void)flags;
    fill_bytes((unsigned char *)buffer, length);
    return (ssize_t)length;
}

int getentropy(void *buffer, size_t length) {
    if (length > 256) {
        errno = EIO;
        return -1;
    }
    fill_bytes((unsigned char *)buffer, length);
    return 0;
}
