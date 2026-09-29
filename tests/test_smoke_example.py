"""The smoke child must target the configured instance, not a different host."""
import asyncio
import importlib.util
from pathlib import Path
import pytest

@pytest.mark.parametrize('instance', [None, 'test-other-instance'])
def test_smoke_propagates_instance(monkeypatch, instance):
    path=Path(__file__).parents[1]/'examples/smoke_client.py'
    spec=importlib.util.spec_from_file_location('smoke_example',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    if instance is None:monkeypatch.delenv('CASCADEUR_MCP_INSTANCE',raising=False)
    else:monkeypatch.setenv('CASCADEUR_MCP_INSTANCE',instance)
    class Observed(Exception):pass
    def inspect(params):
        assert params.env=={'CASCADEUR_MCP_INSTANCE':instance or 'c01'}
        raise Observed()
    monkeypatch.setattr(module,'stdio_client',inspect)
    with pytest.raises(Observed):asyncio.run(module.smoke())
