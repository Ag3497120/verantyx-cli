use tokenizers::Tokenizer;
use std::ffi::{CStr, CString};
use std::os::raw::c_char;

pub struct JCrossTokenizer {
    tokenizer: Tokenizer,
}

#[unsafe(no_mangle)]
pub extern "C" fn jcross_tokenizer_create(path: *const c_char) -> *mut JCrossTokenizer {
    if path.is_null() { return std::ptr::null_mut(); }
    let c_str = unsafe { CStr::from_ptr(path) };
    let path_str = match c_str.to_str() {
        Ok(s) => s,
        Err(_) => return std::ptr::null_mut(),
    };
    
    match Tokenizer::from_file(path_str) {
        Ok(tokenizer) => {
            let j_tokenizer = Box::new(JCrossTokenizer { tokenizer });
            Box::into_raw(j_tokenizer)
        },
        Err(_) => std::ptr::null_mut(),
    }
}

#[unsafe(no_mangle)]
pub extern "C" fn jcross_tokenizer_decode(
    tokenizer_ptr: *mut JCrossTokenizer,
    token_id: u32
) -> *mut c_char {
    if tokenizer_ptr.is_null() { return std::ptr::null_mut(); }
    let tokenizer = unsafe { &*tokenizer_ptr };
    
    match tokenizer.tokenizer.decode(&[token_id], true) {
        Ok(text) => {
            match CString::new(text) {
                Ok(c_string) => c_string.into_raw(),
                Err(_) => std::ptr::null_mut(),
            }
        },
        Err(_) => std::ptr::null_mut(),
    }
}

#[unsafe(no_mangle)]
pub extern "C" fn jcross_tokenizer_free_string(s: *mut c_char) {
    if !s.is_null() {
        unsafe { let _ = CString::from_raw(s); }
    }
}

#[unsafe(no_mangle)]
pub extern "C" fn jcross_tokenizer_destroy(tokenizer_ptr: *mut JCrossTokenizer) {
    if !tokenizer_ptr.is_null() {
        unsafe { let _ = Box::from_raw(tokenizer_ptr); }
    }
}

#[unsafe(no_mangle)]
pub extern "C" fn jcross_tokenizer_encode(
    tokenizer_ptr: *mut JCrossTokenizer,
    text: *const c_char,
    out_len: *mut usize
) -> *mut u32 {
    if tokenizer_ptr.is_null() || text.is_null() || out_len.is_null() {
        return std::ptr::null_mut();
    }
    let tokenizer = unsafe { &*tokenizer_ptr };
    let c_str = unsafe { CStr::from_ptr(text) };
    let text_str = match c_str.to_str() {
        Ok(s) => s,
        Err(_) => return std::ptr::null_mut(),
    };
    
    match tokenizer.tokenizer.encode(text_str, true) {
        Ok(encoding) => {
            let mut ids = encoding.get_ids().to_vec();
            unsafe { *out_len = ids.len() };
            let ptr = ids.as_mut_ptr();
            std::mem::forget(ids);
            ptr
        },
        Err(_) => std::ptr::null_mut(),
    }
}

#[unsafe(no_mangle)]
pub extern "C" fn jcross_tokenizer_free_tokens(tokens_ptr: *mut u32, len: usize) {
    if !tokens_ptr.is_null() {
        unsafe { let _ = Vec::from_raw_parts(tokens_ptr, len, len); }
    }
}
