import sqlite3
from datetime import datetime
from typing import Optional, List, Dict
import os

class JobDatabase:
    """Gerencia o banco de dados de jobs de processamento."""
    
    def __init__(self, db_path: str = "jobs.db"):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Inicializa o banco de dados."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL,
                status TEXT NOT NULL,
                progress INTEGER DEFAULT 0,
                message TEXT,
                filename TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                error TEXT,
                checkpoint_text TEXT,
                checkpoint_humanized TEXT,
                checkpoint_stage TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def create_job(self, url: str) -> int:
        """
        Cria um novo job.
        
        Returns:
            ID do job criado
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO jobs (url, status, progress, message)
            VALUES (?, ?, ?, ?)
        ''', (url, 'pending', 0, 'Aguardando processamento'))
        
        job_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return job_id
    
    def update_job(self, job_id: int, status: str = None, progress: int = None, 
                   message: str = None, filename: str = None, error: str = None,
                   checkpoint_text: str = None, checkpoint_humanized: str = None, 
                   checkpoint_stage: str = None):
        """Atualiza um job."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        updates = []
        params = []
        
        if status is not None:
            updates.append("status = ?")
            params.append(status)
            
            if status == 'complete':
                updates.append("completed_at = ?")
                params.append(datetime.now().isoformat())
        
        if progress is not None:
            updates.append("progress = ?")
            params.append(progress)
        
        if message is not None:
            updates.append("message = ?")
            params.append(message)
        
        if filename is not None:
            updates.append("filename = ?")
            params.append(filename)
        
        if error is not None:
            updates.append("error = ?")
            params.append(error)
        
        if checkpoint_text is not None:
            updates.append("checkpoint_text = ?")
            params.append(checkpoint_text)
        
        if checkpoint_humanized is not None:
            updates.append("checkpoint_humanized = ?")
            params.append(checkpoint_humanized)
        
        if checkpoint_stage is not None:
            updates.append("checkpoint_stage = ?")
            params.append(checkpoint_stage)
        
        updates.append("updated_at = ?")
        params.append(datetime.now().isoformat())
        
        params.append(job_id)
        
        query = f"UPDATE jobs SET {', '.join(updates)} WHERE id = ?"
        cursor.execute(query, params)
        
        conn.commit()
        conn.close()
    
    def get_job(self, job_id: int) -> Optional[Dict]:
        """Obtém um job por ID."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
        row = cursor.fetchone()
        
        conn.close()
        
        if row:
            return dict(row)
        return None
    
    def get_all_jobs(self, limit: int = 50) -> List[Dict]:
        """Obtém todos os jobs, ordenados por data de criação."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM jobs 
            ORDER BY created_at DESC 
            LIMIT ?
        ''', (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def get_pending_jobs(self) -> List[Dict]:
        """Obtém jobs pendentes ou em processamento."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM jobs 
            WHERE status IN ('pending', 'fetching', 'humanizing', 'generating')
            ORDER BY created_at ASC
        ''')
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def delete_job(self, job_id: int):
        """Deleta um job."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
        
        conn.commit()
        conn.close()
