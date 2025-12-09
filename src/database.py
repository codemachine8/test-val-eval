"""
Simulated database module with shared state.
This module intentionally has issues that cause order-dependent test failures.
"""

from typing import Dict, List, Optional
import threading


class Database:
    """Simple in-memory database with shared state issues."""
    
    # Class-level shared state - causes order-dependent flakiness
    _instance = None
    _data: Dict[str, dict] = {}
    _connected: bool = False
    _transaction_count: int = 0
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def connect(self) -> bool:
        """Connect to the database."""
        Database._connected = True
        return True
    
    def disconnect(self) -> bool:
        """Disconnect from the database."""
        Database._connected = False
        return True
    
    def is_connected(self) -> bool:
        """Check if connected."""
        return Database._connected
    
    def insert(self, table: str, record: dict) -> int:
        """Insert a record into a table."""
        if not Database._connected:
            raise ConnectionError("Database not connected")
        
        if table not in Database._data:
            Database._data[table] = {}
        
        record_id = len(Database._data[table]) + 1
        Database._data[table][record_id] = record.copy()
        Database._transaction_count += 1
        return record_id
    
    def get(self, table: str, record_id: int) -> Optional[dict]:
        """Get a record by ID."""
        if not Database._connected:
            raise ConnectionError("Database not connected")
        
        if table not in Database._data:
            return None
        return Database._data[table].get(record_id)
    
    def get_all(self, table: str) -> List[dict]:
        """Get all records from a table."""
        if not Database._connected:
            raise ConnectionError("Database not connected")
        
        if table not in Database._data:
            return []
        return list(Database._data[table].values())
    
    def delete(self, table: str, record_id: int) -> bool:
        """Delete a record."""
        if not Database._connected:
            raise ConnectionError("Database not connected")
        
        if table in Database._data and record_id in Database._data[table]:
            del Database._data[table][record_id]
            return True
        return False
    
    def clear_table(self, table: str) -> None:
        """Clear all records from a table."""
        if table in Database._data:
            Database._data[table] = {}
    
    def clear_all(self) -> None:
        """Clear all data."""
        Database._data = {}
        Database._transaction_count = 0
    
    def get_transaction_count(self) -> int:
        """Get total transaction count."""
        return Database._transaction_count


class UserService:
    """Service layer for user operations."""
    
    def __init__(self, db: Database):
        self.db = db
        self._cache: Dict[int, dict] = {}  # Instance cache - also problematic
    
    def create_user(self, name: str, email: str) -> int:
        """Create a new user."""
        user = {"name": name, "email": email, "active": True}
        user_id = self.db.insert("users", user)
        self._cache[user_id] = user
        return user_id
    
    def get_user(self, user_id: int) -> Optional[dict]:
        """Get user by ID, with caching."""
        if user_id in self._cache:
            return self._cache[user_id]
        return self.db.get("users", user_id)
    
    def deactivate_user(self, user_id: int) -> bool:
        """Deactivate a user."""
        user = self.db.get("users", user_id)
        if user:
            user["active"] = False
            # Bug: doesn't update the database, only local copy
            if user_id in self._cache:
                self._cache[user_id]["active"] = False
            return True
        return False
    
    def count_active_users(self) -> int:
        """Count active users."""
        users = self.db.get_all("users")
        return sum(1 for u in users if u.get("active", False))
