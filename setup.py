from setuptools import setup, find_packages

setup(
    name="uvm_gen",
    version="0.1.0",
    packages=find_packages(),
    include_package_data=True,
    package_data={"uvm_gen": ["templates/**/*.j2"]},
    install_requires=["Jinja2>=3.1", "PyYAML>=6.0"],
    entry_points={
        "console_scripts": [
            "gen_tb=uvm_gen.cli:main",
        ],
    },
    python_requires=">=3.8",
)
