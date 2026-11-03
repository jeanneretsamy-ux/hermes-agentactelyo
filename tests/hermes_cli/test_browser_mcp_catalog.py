"""Personal-browser entries must preserve the browser's connection approval."""

import pytest


@pytest.mark.parametrize('name,channel', [('browser-chrome', 'chrome'), ('browser-edge', 'msedge')])
def test_browser_catalog_uses_approved_extension_connection(name, channel):
    from hermes_cli.mcp_catalog import get_entry, _build_server_config

    entry = get_entry(name)
    assert entry is not None
    config = _build_server_config(entry, None)
    args = config['args']
    assert '--extension' in args
    assert args[args.index('--browser') + 1] == channel
    assert any(arg.startswith('@playwright/mcp@') and not arg.endswith('@latest') for arg in args)
    assert not config.get('env', {}).get('PLAYWRIGHT_MCP_EXTENSION_TOKEN')
    assert '--cdp-endpoint' not in args
