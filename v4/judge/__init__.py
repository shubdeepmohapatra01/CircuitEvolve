"""The v4 judge: frozen upstream checks, wrapped once, with the caches v3 did not have.

    frozen.check_frozen()   once per process (v3 re-read and hashed 52 files / 299 KB per verify = 3.3 ms)
    dv.load / measure / verify / verify_window      the v3 judge surface, plus:
        dv.reference(ref)       memoised ReferenceSpec (v3 rebuilt the reference unitary on every call)
        dv.verify_cached(...)   memoised on (normalise(old), normalise(new), mode, bound)
    certify.certify(...)    certificate dispatch (algebraic | exact_ring | numeric_block | branch_kraus)
"""
