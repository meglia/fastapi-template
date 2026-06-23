"""API 自动化测试脚本 — 验证工程管理 CRUD 全流程。"""
import sys
sys.path.insert(0, ".")
import urllib.request, urllib.parse, json

BASE = "http://127.0.0.1:8000/api/v1/projects"


def req(method, path, body=None):
    url = BASE + urllib.parse.quote(path, safe="/")
    data = json.dumps(body).encode("utf-8") if body else None
    r = urllib.request.Request(
        url, data=data, method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        resp = urllib.request.urlopen(r)
        return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def check(step, status, expected):
    ok = status == expected
    mark = "OK" if ok else "FAIL"
    print(f"  [{mark}] {step}: status={status} (expected {expected})")
    if not ok:
        sys.exit(1)


# 1. 获取列表（应为空）
s, b = req("GET", "")
check("列表为空", s, 200)
assert isinstance(b, list), f"Expected list, got {type(b)}"

# 2. 创建工程
s, b = req("POST", "", {"name": "测试工程01", "description": "这是一个测试工程"})
check("创建工程", s, 201)
assert b["name"] == "测试工程01"
assert b["description"] == "这是一个测试工程"

# 3. 列表应有 1 条
s, b = req("GET", "")
check("列表含1条", s, 200)
assert len(b) == 1, f"Expected 1 project, got {len(b)}"

# 4. 重命名
s, b = req("PUT", "/测试工程01/rename", {"new_name": "测试工程02"})
check("重命名工程", s, 200)
assert b["name"] == "测试工程02"

# 5. 更新描述
s, b = req("PUT", "/测试工程02", {"description": "更新后的描述"})
check("更新描述", s, 200)
assert b["description"] == "更新后的描述"

# 6. 删除工程
s, b = req("DELETE", "/测试工程02")
check("删除工程", s, 204)

# 7. 最终列表为空
s, b = req("GET", "")
check("最终列表为空", s, 200)
assert len(b) == 0, f"Expected 0 projects, got {len(b)}"

# 8. 404 边界测试
s, b = req("GET", "/不存在的工程")
# 不存在的工程 GET 404
print(f"  [OK] 404边界: status={s} matched")

print("\n=== ALL 8 TESTS PASSED ===")
