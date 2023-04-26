from setuptools import setup, find_packages


setup(
    name="mana",
    version="1.0.0",
    packages=find_packages("src", exclude=["*tests"]),
    package_dir={"": "src"},
    include_package_data=True,
    install_requires=[
        "pyserial",
        "ephem",
        "Pillow",
        "scapy",
        "numpy",
        "sklearn"
    ],
)