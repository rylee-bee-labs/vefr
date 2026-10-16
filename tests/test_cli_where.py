"""`vefr where` and `vefr explain` - the read-only authoring answers.

Both run against the tracked sample pack (worlds/sample-world) and a copy
of it under tmp_path, so nothing here reads or writes a real pack. The
failure shapes match cmd_find's, on purpose: a refused pack is exit 1
with a named line, a thing the pack defines nowhere is exit 0 with
UNKNOWN on its own line, and a block name the front door does not know
is a refusal that names the ones it does.
"""

import json
import shutil
from pathlib import Path
from types import SimpleNamespace

from vefr.cli import EXIT_ERROR, EXIT_OK, cmd_explain, cmd_where

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / 'worlds' / 'sample-world'


def _where(thing, pack=PACK):
    return cmd_where(SimpleNamespace(thing=thing, pack=str(pack)))


def _explain(block, pack=PACK):
    return cmd_explain(SimpleNamespace(block=block, pack=str(pack)))


def test_a_speaker_is_located_by_its_act_region_and_cell(capsys):
    """The sample world's keeper stands on a tile: where names the act,
    the region and the cell, and only that one line."""
    rc = _where('keeper')
    out = capsys.readouterr().out.splitlines()
    assert rc == EXIT_OK
    assert out == ['speaker keeper: act-1/town at 7,4']


def test_a_named_place_is_located_by_its_map_cell(capsys):
    """A point of interest is a map cell whose `pois` value is the name:
    where answers with the cell the map draws it on."""
    rc = _where('the stone')
    out = capsys.readouterr().out.splitlines()
    assert rc == EXIT_OK
    assert out == ['place the stone: act-1/town at 7,3']


def test_an_item_is_located_in_the_catalog(capsys):
    """An item has no cell of its own; where says so plainly rather than
    inventing one."""
    rc = _where('torch')
    out = capsys.readouterr().out.splitlines()
    assert rc == EXIT_OK
    assert out == ['item torch: the pack catalog (world.json)']


def test_a_thing_the_pack_does_not_define_prints_unknown_and_exits_zero(capsys):
    rc = _where('zzzznotinthepack')
    out = capsys.readouterr().out
    assert rc == EXIT_OK
    assert out.strip() == 'UNKNOWN'


def test_a_missing_pack_is_refused_distinctly(capsys):
    missing = ROOT / 'worlds' / 'no-such-pack-where'
    rc = _where('keeper', pack=missing)
    out = capsys.readouterr().out
    assert rc == EXIT_ERROR
    assert 'pack not found' in out
    assert 'UNKNOWN' not in out


def test_an_enemy_is_located_by_its_act_region_and_cell(tmp_path, capsys):
    """A pack that names an enemy gets the act, the region and the tile its
    contract puts it on - the record the player bakes as a spawn."""
    pack = tmp_path / 'pack'
    shutil.copytree(PACK, pack)
    contract = pack / 'acts' / 'act-1' / 'town' / 'contract.json'
    data = json.loads(contract.read_text(encoding='utf-8'))
    data['enemies'] = [{'id': 'pit-rat', 'name': 'a pit rat', 'at': [4, 5]}]
    contract.write_text(json.dumps(data), encoding='utf-8')

    rc = _where('pit-rat', pack=pack)
    out = capsys.readouterr().out.splitlines()
    assert rc == EXIT_OK
    assert out == ['enemy pit-rat: act-1/town at 4,5']


def test_explain_prints_the_resolved_block_and_ok_when_it_is_clean(capsys):
    """A declared block comes through as the loader resolved it, and a
    block with no sentences prints `ok` - declaring one is not a fault."""
    rc = _explain('grammars')
    out = capsys.readouterr().out
    assert rc == EXIT_OK
    assert '"whisper"' in out                      # the resolved block, as JSON
    assert out.splitlines()[-1] == 'ok'


def test_explain_reads_a_block_the_pack_does_not_declare_as_null(capsys):
    rc = _explain('skin')
    out = capsys.readouterr().out
    assert rc == EXIT_OK
    assert out.splitlines()[0] == 'null'


def test_explain_prints_a_broken_blocks_own_sentence(tmp_path, capsys):
    """The sentences beside the block are the validator's own: a block the
    pack got wrong prints the same sentence `vefr check` would."""
    pack = tmp_path / 'pack'
    shutil.copytree(PACK, pack)
    world = json.loads((pack / 'world.json').read_text(encoding='utf-8'))
    world['saves'] = {'rules': 'nope'}
    (pack / 'world.json').write_text(json.dumps(world), encoding='utf-8')

    rc = _explain('saves', pack=pack)
    out = capsys.readouterr().out.splitlines()
    assert rc == EXIT_OK
    assert '"nope"' in out[1]                      # the resolved block
    assert out[-1] == 'saves.rules must be "persist" or "reset"'


def test_an_unknown_block_is_refused_with_the_list_of_known_ones(capsys):
    rc = _explain('not-a-block')
    out = capsys.readouterr().out
    assert rc == EXIT_ERROR
    assert 'no such block' in out
    for name in ('growth', 'spells', 'skin', 'rules'):
        assert name in out, name


def test_a_missing_pack_is_refused_for_explain_too(capsys):
    missing = ROOT / 'worlds' / 'no-such-pack-explain'
    rc = _explain('skin', pack=missing)
    out = capsys.readouterr().out
    assert rc == EXIT_ERROR
    assert 'pack not found' in out
