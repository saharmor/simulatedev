#!/usr/bin/env python3
"""
Workflows Package

This package contains specialized workflow modules for different use cases,
each extending the AgentOrchestrator with specific functionality.
"""

from .bug_hunting import BugHunter
from .general_coding import GeneralCodingWorkflow
from .code_optimization import CodeOptimizer
from .test_workflow import TestWorkflow

__all__ = [
    'BugHunter',
    'GeneralCodingWorkflow', 
    'CodeOptimizer',
    'TestWorkflow'
] 