"""Closed input wrapper for campaigns using actual wheel-owned executables.

The ordinary artifact verifier is unchanged. Integration adds this explicit
installed branch, retains its complete evidence beside the existing campaign
receipt, and compares the unchanged native projection across runtime slots.
This helper performs no acceptance, subprocess execution or filesystem repair.
"""
from __future__ import annotations
from pathlib import Path

if __package__:
    from .check_realization_binaries import verify_installed
else:
    from check_realization_binaries import verify_installed


def require(condition, message):
    if not condition:
        raise ValueError(message)


class InstalledCampaignInputs:
    def __init__(self, *, native_root, revision, target, source_revision, run_id, core, verify):
        self.arguments = dict(directory=Path(native_root), revision=revision, target=target,
            source_revision=source_revision, run_id=run_id, core=Path(core), verify_binary=Path(verify))
        self.before = verify_installed(**self.arguments)
        self.completed = False

    @property
    def core(self):
        return self.arguments['core']

    @property
    def verify(self):
        return self.arguments['verify_binary']

    @property
    def native(self):
        # A fresh deep JSON tree, so callers cannot alter the independent before
        # receipt by inserting mutable fields into their existing campaign proof.
        import json
        return json.loads(json.dumps(self.before['native']))

    def finish(self):
        require(not self.completed, 'Installed campaign proof already finalized')
        after = verify_installed(**self.arguments)
        require(after == self.before, 'Installed campaign owned inputs changed during execution')
        self.completed = True
        return {'schema_version': 'biocompiler.installed_campaign_inputs.v1',
            'status': 'pass', 'input_layout': 'installed', 'before': self.before, 'after': after,
            'core': str(self.core), 'verify': str(self.verify)}
