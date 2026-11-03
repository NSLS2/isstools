# ISS Tiled integration checks

Run the focused tests in the beamline Python environment:

```bash
python -m pytest -q isstools/tests/test_tiled_access.py
python -m unittest -v isstools.tests.test_tiled_validation_integration
python -m pytest -q ../issxas/xas/tests/test_tiled_db_io.py
```

For a beamline smoke test, start the profile collection and verify that XLive
opens, the Processing tab lists runs for the selected proposal and cycle, and
both a new scan and a selected historical scan can be processed. Check the
generated data and plots against the previous Databroker output. Include a
step scan, an APB fly scan, an EPICS fly scan, and runs with each applicable
Pilatus, Xspress and Ge detector; test Pilatus image loading if used.

The GUI's authenticated client is `xlive_tiled_client`, already scoped to
`iss/migration`. ISS processing uses an independent plugin-dispatch catalog
with the same authenticated context, and passes its v2/v1 interface to the
existing analysis functions. Tiled handles external assets on the server; migration runs use the
MIME-type and resource/datum patches in `startup/02-tiled-writer.py`. The
RunEngine subscribes one TiledWriter to the shared migration writing client.
For new runs, XLive waits for the persisted Stop using a WebSocket subscription
to the migration catalog, then validates and processes the run. Confirm Tiled
streaming is enabled and that the GUI user's session can subscribe to it.
For each completed experimental run, processing validates and repairs external
data-source shapes using the authenticated GUI client before reading. Verify
that the logged-in user is authorized for the Tiled validation endpoint; it
requires `read:data`, `read:metadata`, and `write:metadata` on the run.
Test historical XIA_XMAP_HDF5 and XSP3X runs separately to check their migration
and server-side adapter coverage.

Some profile-collection plans still use the old global `db`, including tuning,
offset/gain optimization and Johann alignment. These need a separate migration
to the acquisition reading client and explicit waiting for the particular run
before they can be exercised without a Databroker global.
