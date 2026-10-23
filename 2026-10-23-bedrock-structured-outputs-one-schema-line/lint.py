"""Check a JSON schema against the Bedrock structured-outputs subset as DOCUMENTED on
https://docs.aws.amazon.com/bedrock/latest/userguide/structured-output.html (fetched 2026-10-23).
This is a reading of the doc, not Bedrock's validator."""
UNSUPPORTED_KEYS = {"minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "multipleOf",
                    "minLength", "maxLength"}
FORMATS = {"date-time", "time", "date", "duration", "email", "hostname", "uri", "ipv4", "ipv6", "uuid"}

def lint(schema):
    problems = []
    defs = schema.get("$defs", {})
    def walk(s, path, stack):
        if not isinstance(s, dict): return
        ref = s.get("$ref")
        if ref:
            if not ref.startswith("#/"): problems.append(f"{path}: external $ref {ref}")
            name = ref.split("/")[-1]
            if name in stack: problems.append(f"{path}: recursive $ref to {name}"); return
            walk(defs.get(name, {}), path + f"->{name}", stack | {name})
        for k in UNSUPPORTED_KEYS & s.keys(): problems.append(f"{path}: {k}={s[k]}")
        if s.get("type") == "object" or "properties" in s:
            ap = s.get("additionalProperties", "<missing>")
            if ap is not False: problems.append(f"{path}: additionalProperties={ap if ap=='<missing>' else 'schema'}")
        if "minItems" in s and s["minItems"] not in (0, 1): problems.append(f"{path}: minItems={s['minItems']}")
        if "format" in s and s["format"] not in FORMATS: problems.append(f"{path}: format={s['format']}")
        for k, v in s.get("properties", {}).items(): walk(v, f"{path}.{k}", stack)
        if isinstance(s.get("items"), dict): walk(s["items"], path + "[]", stack)
        if isinstance(s.get("additionalProperties"), dict): walk(s["additionalProperties"], path + "{*}", stack)
        for k in ("anyOf", "allOf", "oneOf"):
            for i, v in enumerate(s.get(k, [])): walk(v, f"{path}.{k}[{i}]", stack)
    walk(schema, "$", frozenset())
    return problems
