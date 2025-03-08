from setuptools import setup, find_packages

with open("requirements.txt") as f:
    requirements = f.read().splitlines()

setup(
    name="crawlnchat",
    version="0.1.1",
    description="CrawlnChat: A web crawler with chat interface",
    author="jroakes",
    packages=find_packages(),
    install_requires=requirements,
    python_requires=">=3.8",
    entry_points={
        "console_scripts": [
            "crawlnchat=src.main:main",
        ],
    },
    package_data={
        "": ["*.json", "*.yaml", "*.yml"],
    },
    include_package_data=True,
) 