import pytest
from homeai.security.vision import analyze_snapshot


@pytest.mark.asyncio
async def test_cloud_vision_requires_opt_in():
    with pytest.raises(PermissionError):
        await analyze_snapshot(b"not an image")
