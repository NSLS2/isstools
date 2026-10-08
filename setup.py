from pathlib import Path
import sys

import setuptools

ROOT = Path(__file__).resolve().parent
# PEP 517 build isolation does not put the source tree on sys.path.
sys.path.insert(0, str(ROOT))
import versioneer

requirements = [
    line.strip()
    for line in (ROOT / "requirements.txt").read_text().splitlines()
    if line.strip() and not line.lstrip().startswith("#")
]

setuptools.setup(
    name="isstools",
    version=versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass(),
    description="Qt GUI tools for the ISS beamline",
    long_description=(ROOT / "README.md").read_text(),
    long_description_content_type="text/markdown",
    license="BSD-3-Clause",
    url="https://github.com/NSLS2/isstools",
    packages=setuptools.find_packages(),
    python_requires=">=3.12",
    package_data={"isstools": [
        "dialogs/*.ui", "ui/*.ui", "*.json", "elements/*.ui",
        "schemas/*.json", "icons/*.png", "icons/*.svg", "Resources/*.png",
    ]},
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3 :: Only",
    ],
    install_requires=requirements,
    extras_require={
        "dev": ["build>=1.2", "pytest>=8", "pytest-qt>=4.4"],
        "legacy-pilatus": ["nslsii>=0.11"],
    },
)
