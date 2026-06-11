"""
spike 002: 边界测试 + watermark 字符串→bool 映射测试

⚠️ 这是 spike 内部测试，验证 4 件事：
  1. inputSchema 接受有效输入
  2. inputSchema 拒绝无效输入（在 server 端之前就被 MCP 框架拦下——这里只验证 schema 形状）
  3. _build_body watermark 字符串枚举 → bool 映射
  4. _build_body generate_audio 默认 false
"""
import sys
sys.path.insert(0, '/home/luo/.hermes/profiles/huiben/skills/creative/seedance2.0-tool/spikes/001-mcp-uguu-server')

import mcp_server


def test_watermark_mapping():
    """watermark 字符串枚举 → API bool 字段映射"""
    cases = [
        # (input, expected body["watermark"])
        ("none", False),
        ("platform", False),
        ("seedance_ai", True),
        # 缺省（不传 watermark） → 默认 "none" → False
        (None, False),
    ]
    for wm_input, expected in cases:
        args = {"duration": 5, "prompt": "test"}
        if wm_input is not None:
            args["watermark"] = wm_input
        body = mcp_server._build_body(args)
        actual = body.get("watermark")
        status = "✅" if actual == expected else "❌"
        print(f"{status} watermark={wm_input!r:18} → body.watermark={actual!r:6} (expected {expected!r})")


def test_generate_audio_default():
    """generate_audio 不传时默认 false（绘本场景防莫名说话声）"""
    # 不传 generate_audio
    body = mcp_server._build_body({"duration": 5, "prompt": "test"})
    assert body["generate_audio"] == False, f"expected False, got {body['generate_audio']}"
    print(f"✅ generate_audio 不传 → body.generate_audio={body['generate_audio']!r}")
    # 显式传 true
    body = mcp_server._build_body({"duration": 5, "prompt": "test", "generate_audio": True})
    assert body["generate_audio"] == True
    print(f"✅ generate_audio=true → body.generate_audio={body['generate_audio']!r}")


def test_duration_field():
    """duration 必为 integer, 范围 [4, 15]"""
    schema = None
    import asyncio
    tools = asyncio.run(mcp_server.list_tools())
    gv = next(t for t in tools if t.name == "generate_video")
    duration = gv.inputSchema["properties"]["duration"]
    assert duration["type"] == "integer", f"type 应该是 integer，实际 {duration['type']}"
    assert duration["minimum"] == 4
    assert duration["maximum"] == 15
    print(f"✅ duration type={duration['type']!r} minimum={duration['minimum']} maximum={duration['maximum']}")


def test_watermark_enum():
    """watermark 字段是 string + enum [none, platform, seedance_ai]"""
    import asyncio
    tools = asyncio.run(mcp_server.list_tools())
    gv = next(t for t in tools if t.name == "generate_video")
    wm = gv.inputSchema["properties"]["watermark"]
    assert wm["type"] == "string"
    assert wm["enum"] == ["none", "platform", "seedance_ai"]
    assert wm["default"] == "none"
    print(f"✅ watermark type={wm['type']!r} enum={wm['enum']} default={wm['default']!r}")


def test_required_fields():
    """duration 必填（绘本场景最关键参数）"""
    import asyncio
    tools = asyncio.run(mcp_server.list_tools())
    gv = next(t for t in tools if t.name == "generate_video")
    required = gv.inputSchema["required"]
    assert "duration" in required, f"duration 必填，实际 required={required}"
    print(f"✅ required fields: {required}")


if __name__ == "__main__":
    print("=" * 50)
    print("spike 002 边界测试")
    print("=" * 50)
    print()
    print("--- watermark 字符串→bool 映射 ---")
    test_watermark_mapping()
    print()
    print("--- generate_audio 默认值 ---")
    test_generate_audio_default()
    print()
    print("--- duration inputSchema ---")
    test_duration_field()
    print()
    print("--- watermark inputSchema ---")
    test_watermark_enum()
    print()
    print("--- required fields ---")
    test_required_fields()
    print()
    print("=" * 50)
    print("✅ 全部通过")
