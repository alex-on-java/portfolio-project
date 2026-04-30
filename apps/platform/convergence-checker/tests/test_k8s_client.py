from __future__ import annotations

from unittest.mock import MagicMock

from kubernetes import client as k8s_client

from convergence_checker import k8s_client as k8s


class TestPatchConfigmap:
    def test_propagates_field_manager_to_sdk(self) -> None:
        api = MagicMock(spec=k8s_client.CoreV1Api)

        k8s.patch_configmap(
            api,
            name="any-cm",
            namespace="any-ns",
            data={"k": "v"},
            field_manager="test-manager",
        )

        api.patch_namespaced_config_map.assert_called_once()
        kwargs = api.patch_namespaced_config_map.call_args.kwargs
        assert kwargs["field_manager"] == "test-manager"
        assert kwargs["name"] == "any-cm"
        assert kwargs["namespace"] == "any-ns"
        assert kwargs["body"].data == {"k": "v"}
