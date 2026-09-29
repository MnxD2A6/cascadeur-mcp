"""Protect only the dedicated bridge directory, using OS APIs rather than shell.

Windows API sources:
https://learn.microsoft.com/en-us/windows/win32/api/aclapi/nf-aclapi-setnamedsecurityinfow
https://learn.microsoft.com/en-us/windows/win32/secauthz/sid-strings
"""

import os


def make_private(path):
    if os.name != "nt":
        path.chmod(0o700)
        return
    import ctypes as c
    from ctypes import wintypes as w

    advapi = c.WinDLL("advapi32", use_last_error=True)
    kernel = c.WinDLL("kernel32", use_last_error=True)
    convert = advapi.ConvertStringSecurityDescriptorToSecurityDescriptorW
    convert.argtypes = [w.LPCWSTR, w.DWORD, c.POINTER(c.c_void_p), c.POINTER(w.DWORD)]
    convert.restype = w.BOOL
    get_dacl = advapi.GetSecurityDescriptorDacl
    get_dacl.argtypes = [c.c_void_p, c.POINTER(w.BOOL), c.POINTER(c.c_void_p), c.POINTER(w.BOOL)]
    get_dacl.restype = w.BOOL
    set_info = advapi.SetNamedSecurityInfoW
    set_info.argtypes = [w.LPWSTR, c.c_int, w.DWORD, c.c_void_p, c.c_void_p, c.c_void_p, c.c_void_p]
    set_info.restype = w.DWORD
    kernel.LocalFree.argtypes = [c.c_void_p]
    kernel.LocalFree.restype = c.c_void_p
    descriptor, acl = c.c_void_p(), c.c_void_p()
    present, defaulted = w.BOOL(), w.BOOL()
    # Protected DACL: owner rights and SYSTEM only, inherited by new children.
    if not convert("D:P(A;OICI;FA;;;OW)(A;OICI;FA;;;SY)", 1, c.byref(descriptor), None):
        raise c.WinError(c.get_last_error())
    try:
        if not get_dacl(descriptor, c.byref(present), c.byref(acl), c.byref(defaulted)):
            raise c.WinError(c.get_last_error())
        if not present or not acl:
            raise RuntimeError("PRIVATE_DIRECTORY_FAILED: no restrictive DACL")
        error = set_info(str(path), 1, 0x80000004, None, None, acl, None)
        if error:
            raise c.WinError(error)
    finally:
        kernel.LocalFree(descriptor)
