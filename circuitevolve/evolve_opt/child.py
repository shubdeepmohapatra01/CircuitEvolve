"""LEGACY compatibility entry point; moved to circuitevolve.legacy.evolve_opt.child."""
import sys

from circuitevolve.legacy.evolve_opt.child import main

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
