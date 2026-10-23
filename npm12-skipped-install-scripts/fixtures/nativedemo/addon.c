#include <node_api.h>

static napi_value Hello(napi_env env, napi_callback_info info) {
  napi_value out;
  napi_create_string_utf8(env, "native ok", NAPI_AUTO_LENGTH, &out);
  return out;
}

NAPI_MODULE_INIT() {
  napi_value fn;
  napi_create_function(env, "hello", NAPI_AUTO_LENGTH, Hello, NULL, &fn);
  napi_set_named_property(env, exports, "hello", fn);
  return exports;
}
