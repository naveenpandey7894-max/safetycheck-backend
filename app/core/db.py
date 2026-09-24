"""Single shared Prisma client instance, connected on app startup and
disconnected on shutdown (see app/main.py)."""
from prisma import Prisma

prisma = Prisma()
