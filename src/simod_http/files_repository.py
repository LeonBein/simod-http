import hashlib
from abc import abstractmethod, ABCMeta
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class File:
    file_name: str
    content: bytes
    sha256: str
    _id: Optional[str] = None


class FilesRepositoryInterface(metaclass=ABCMeta):
    @abstractmethod
    def file_path(self, file_name: str) -> Path:
        pass

    @abstractmethod
    def create(self, content: bytes, suffix: str) -> File:
        pass

    @abstractmethod
    def get_by_id(self, file_id: str) -> Optional[File]:
        pass

    @abstractmethod
    def get_by_sha256(self, sha256: str) -> Optional[File]:
        pass

    @abstractmethod
    def does_exist(self, sha256: str) -> bool:
        pass

    @abstractmethod
    def delete(self, file_id: str):
        pass


def compute_sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()
