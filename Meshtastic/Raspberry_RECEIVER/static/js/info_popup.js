// Info button and popup functionality
document.getElementById('infoButton').addEventListener('click', function() {
  // Create popup overlay
  const overlay = document.createElement('div');
  overlay.style.position = 'fixed';
  overlay.style.top = '0';
  overlay.style.left = '0';
  overlay.style.width = '100%';
  overlay.style.height = '100%';
  overlay.style.backgroundColor = 'rgba(0, 0, 0, 0.5)';
  overlay.style.display = 'flex';
  overlay.style.alignItems = 'center';
  overlay.style.justifyContent = 'center';
  overlay.style.zIndex = '1000';
  overlay.id = 'infoOverlay';

  // Create popup content box
  const popup = document.createElement('div');
  popup.style.backgroundColor = 'white';
  popup.style.padding = '20px';
  popup.style.borderRadius = '8px';
  popup.style.maxWidth = '600px';
  popup.style.maxHeight = '80vh';
  popup.style.overflowY = 'auto';
  popup.style.boxShadow = '0 4px 8px rgba(0, 0, 0, 0.2)';
  popup.style.position = 'relative';

  // Add close button
  const closeButton = document.createElement('button');
  closeButton.innerText = 'X';
  closeButton.style.position = 'absolute';
  closeButton.style.top = '10px';
  closeButton.style.right = '10px';
  closeButton.style.backgroundColor = '#ff0000';
  closeButton.style.color = 'white';
  closeButton.style.border = 'none';
  closeButton.style.borderRadius = '50%';
  closeButton.style.width = '24px';
  closeButton.style.height = '24px';
  closeButton.style.cursor = 'pointer';
  closeButton.addEventListener('click', function() {
    document.body.removeChild(overlay);
  });
  popup.appendChild(closeButton);

  // Add title
  const title = document.createElement('h2');
  title.innerText = 'Spiegazione di Hops, RSSI e SNR per Meshtastic';
  title.style.color = '#007bff';
  title.style.marginTop = '0';
  popup.appendChild(title);

  // Add content
  const content = document.createElement('pre');
  content.style.whiteSpace = 'pre-wrap';
  content.style.fontFamily = 'inherit';
  content.innerText = `
Spiegazione di Hops, RSSI e SNR per Meshtastic

1. Hops (Salti)
Gli "hops" rappresentano il numero di nodi intermedi attraverso cui un messaggio passa prima di raggiungere il dispositivo ricevente in una rete mesh come Meshtastic. Ogni volta che un messaggio viene ritrasmesso da un nodo a un altro, il conteggio degli hops aumenta di 1.

- Hops: 0
  Significa che il messaggio è arrivato direttamente dal mittente al ricevente senza passare attraverso alcun nodo intermedio. Questo indica una connessione diretta tra i due dispositivi, spesso perché sono vicini o non ci sono ostacoli significativi.

- Hops: 1 o più
  Indica che il messaggio ha dovuto passare attraverso uno o più nodi intermedi per raggiungere il ricevente. Un numero maggiore di hops può significare una distanza maggiore tra mittente e ricevente o la presenza di ostacoli che impediscono una connessione diretta. In generale, un numero di hops basso (ad esempio 1 o 2) è preferibile perché significa meno ritrasmissioni, riducendo la latenza e il rischio di perdita di dati. Tuttavia, in una rete mesh, avere più hops è normale e dimostra la capacità della rete di trovare percorsi alternativi.

2. RSSI (Received Signal Strength Indicator - Indicatore di Forza del Segnale Ricevuto)
L'RSSI misura la potenza del segnale radio ricevuto dal dispositivo, espressa in decibel milliwatt (dBm). È un indicatore della forza del segnale al momento della ricezione.

- Valori di RSSI:
  - Da -30 a -50 dBm: Segnale eccellente. Questo indica una connessione molto forte, tipica di dispositivi molto vicini o con una linea di vista chiara.
  - Da -50 a -70 dBm: Segnale buono. Questo è un intervallo comune per una connessione affidabile in condizioni normali.
  - Da -70 a -90 dBm: Segnale debole. La connessione potrebbe essere instabile, con possibile perdita di pacchetti o necessità di ritrasmissioni. Tuttavia, valori in questo intervallo possono ancora funzionare, specialmente se non ci sono interferenze.
  - Inferiore a -90 dBm: Segnale molto debole. La comunicazione potrebbe essere inaffidabile o intermittente. In questi casi, è probabile che i messaggi non arrivino correttamente senza l'intervento di nodi intermedi per ritrasmettere.

Un RSSI più alto (cioè meno negativo, come -50 rispetto a -80) indica un segnale più forte e una migliore qualità della connessione.

3. SNR (Signal-to-Noise Ratio - Rapporto Segnale-Rumore)
L'SNR misura il rapporto tra la potenza del segnale utile e il rumore di fondo, espresso in decibel (dB). Un valore di SNR più alto indica che il segnale è più chiaro rispetto al rumore, migliorando la qualità della comunicazione.

- Valori di SNR:
  - Sopra 20 dB: Eccellente. Il segnale è molto chiaro rispetto al rumore di fondo, garantendo una comunicazione affidabile.
  - Da 10 a 20 dB: Buono. Il segnale è ancora chiaramente distinguibile dal rumore, e la comunicazione è generalmente stabile.
  - Da 0 a 10 dB: Accettabile. Il segnale è più vicino al livello di rumore, il che potrebbe causare qualche errore o perdita di dati, ma la comunicazione può ancora funzionare.
  - Inferiore a 0 dB: Scarso. Il rumore supera il segnale, rendendo la comunicazione molto difficile o inaffidabile. In questi casi, è probabile che i messaggi non vengano ricevuti correttamente.

Conclusione
Per una comunicazione ottimale con Meshtastic, idealmente si dovrebbero avere:
- Hops: 0 o 1, per una trasmissione diretta o con un solo nodo intermedio.
- RSSI: superiore a -70 dBm, per garantire un segnale forte.
- SNR: superiore a 10 dB, per assicurare che il segnale sia chiaramente distinguibile dal rumore.

Questi valori indicano una connessione affidabile. Tuttavia, la rete mesh di Meshtastic è progettata per funzionare anche in condizioni meno ideali, utilizzando nodi intermedi per ritrasmettere i messaggi quando necessario. Monitorare questi parametri può aiutare a ottimizzare il posizionamento dei dispositivi e a diagnosticare problemi di connessione.
  `;
  popup.appendChild(content);

  // Add popup to overlay
  overlay.appendChild(popup);

  // Add overlay to body
  document.body.appendChild(overlay);
});
