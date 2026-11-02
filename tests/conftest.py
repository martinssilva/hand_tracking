"""Deixa `apps` importavel quando o pytest roda da raiz do repositorio."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
