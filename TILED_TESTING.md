# ISS Tiled integration checks

Run the focused tests in the beamline Python environment:

```bash
python -m pytest -q isstools/tests/test_tiled_access.py
python -m pytest -q ../issxas/xas/tests/test_tiled_db_io.py
```

For a beamline smoke test, start the profile collection and verify that XLive
opens, the Processing tab lists runs for the selected proposal and cycle, and
both a new scan and a selected historical scan can be processed. Check the
generated data and plots against the previous Databroker output. Include a
step scan, an APB fly scan, an EPICS fly scan, and runs with each applicable
Pilatus, Xspress and Ge detector; test Pilatus image loading if used.

The GUI's authenticated client is `xlive_tiled_client`, already scoped to
`iss/migration`. The existing ISS processing and Johann analysis functions require
the Databroker v1 interface and use `xlive_tiled_client.v2.v1` at that
boundary. Tiled handles external assets on the server; migration runs use the
MIME-type and resource/datum patches in `startup/02-tiled-writer.py`. The
RunEngine subscribes one TiledWriter to the shared migration writing client.
Test historical XIA_XMAP_HDF5 and XSP3X runs separately to check their migration
and server-side adapter coverage.

Some profile-collection plans still use the old global `db`, including tuning,
offset/gain optimization and Johann alignment. These need a separate migration
to the acquisition reading client and explicit waiting for the particular run
before they can be exercised without a Databroker global.
