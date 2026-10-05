/* POSIX-only descriptor bridge. No path, process, network or semantic operation.
 * OCaml Unix.file_descr is a POSIX descriptor on the two supported CI platforms.
 * Duplicate above every supplied number so a closed input cannot be resurrected
 * by an earlier duplicate. Validate the duplicate's actual access flags, not a
 * /dev/fd pathname reopen (whose semantics differ between Linux and macOS). */
#include <caml/mlvalues.h>
#include <caml/fail.h>
#include <fcntl.h>
#include <limits.h>
#include <unistd.h>

CAMLprim value bioc_package_duplicate_checked(value fd_value, value minimum_value,
                                               value writing_value)
{
  intnat raw_fd = Long_val(fd_value);
  intnat raw_minimum = Long_val(minimum_value);
  if (raw_fd <= 2 || raw_fd >= INT_MAX || raw_minimum <= raw_fd ||
      raw_minimum > INT_MAX)
    caml_invalid_argument("Invalid artifact descriptor range");
  int duplicated = fcntl((int)raw_fd, F_DUPFD_CLOEXEC, (int)raw_minimum);
  if (duplicated < 0) caml_failwith("Cannot duplicate inherited artifact descriptor");
  int flags = fcntl(duplicated, F_GETFL);
  int access_mode = flags & O_ACCMODE;
  int valid = flags >= 0 && (Bool_val(writing_value)
    ? ((access_mode == O_WRONLY || access_mode == O_RDWR) && !(flags & O_APPEND))
    : access_mode == O_RDONLY);
  if (!valid) {
    close(duplicated);
    caml_invalid_argument("Inherited artifact descriptor has invalid access mode");
  }
  return Val_int(duplicated);
}
