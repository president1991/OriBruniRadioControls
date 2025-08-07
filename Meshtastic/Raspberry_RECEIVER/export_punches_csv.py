from flask import Blueprint, Response
import mysql.connector
from mysql.connector import pooling
import csv
from io import StringIO
import logging

# Configura logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Configurazione del database (adatta in base al tuo setup)
DB_CONFIG = {
    'host': 'localhost',
    'port': '3306',
    'user': 'meshdash',
    'password': 'PuhA7gWCrW',  # Sostituisci con la password corretta
    'database': 'OriBruniRadioControls',
    'charset': 'utf8mb4'
}

export_bp = Blueprint('export', __name__)

def setup_db_pool():
    """Configura il pool di connessioni MySQL"""
    try:
        logging.info("Configurazione del pool di connessioni MySQL per export...")
        pool = pooling.MySQLConnectionPool(
            pool_name="export_pool",
            pool_size=5,
            host=DB_CONFIG['host'],
            port=int(DB_CONFIG['port']),
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            database=DB_CONFIG['database'],
            charset=DB_CONFIG['charset']
        )
        logging.info("Pool di connessioni MySQL per export configurato con successo.")
        return pool
    except Exception as e:
        logging.error(f"Errore durante la configurazione del pool MySQL per export: {str(e)}")
        raise

@export_bp.route('/export_punches_csv')
def export_punches_csv():
    try:
        db_pool = setup_db_pool()
        cnx = db_pool.get_connection()
        cursor = cnx.cursor(dictionary=True)
        
        # Query per ottenere solo i campi richiesti dalla tabella punches
        query = "SELECT punch_time, record_id, control, card_number FROM punches ORDER BY timestamp DESC"
        cursor.execute(query)
        punches = cursor.fetchall()
        
        # Crea un buffer di stringa per il CSV
        output = StringIO()
        writer = csv.writer(output, lineterminator='\n')
        
        # Scrivi l'intestazione del CSV
        headers = ['punch_time', 'record_id', 'control', 'card_number']
        writer.writerow(headers)
        
        # Scrivi i dati nel CSV
        for punch in punches:
            writer.writerow([punch['punch_time'], punch['record_id'], punch['control'], punch['card_number']])
        
        # Prepara la risposta con il file CSV
        response = Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={
                'Content-Disposition': 'attachment; filename=punches_export.csv',
                'Content-Type': 'text/csv; charset=utf-8'
            }
        )
        
        cursor.close()
        cnx.close()
        return response
        
    except Exception as e:
        logging.error(f"Errore durante l'esportazione dei dati in CSV: {str(e)}")
        return Response(
            "Errore durante l'esportazione dei dati. Controlla i log per dettagli.",
            status=500,
            mimetype='text/plain'
        )
