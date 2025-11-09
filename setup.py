from setuptools import setup, find_packages

setup(
    name='queuectl',
    version='1.0.0',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'click>=8.1.0',
    ],
    entry_points={
        'console_scripts': [
            'queuectl=queuectl.cli:cli',
        ],
    },
    author='Your Name',
    description='A CLI-based background job queue system',
    python_requires='>=3.8',
)
