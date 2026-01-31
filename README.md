# OtherProteins - Kirol Osagarrien E-commerce

Flask-ekin garatutako e-commerce web aplikazioa kirol osagarriak eta nutrizio produktuak saltzeko. Interfazea euskaraz dago eta produktuen kudeaketa, erosketa saskia, eskaerak eta fakturazioa eskaintzen ditu.

## 📋 Eduki Taula

- [Proiektuaren Deskribapena](#-proiektuaren-deskribapena)
- [Ezaugarriak](#-ezaugarriak)
- [Sistema Eskakizunak](#-sistema-eskakizunak)
- [Instalazioa](#-instalazioa)
- [Konfigurazioa](#-konfigurazioa)
- [Erabilera](#-erabilera)
- [Proiektuaren Egitura](#-proiektuaren-egitura)
- [Erabilitako Teknologiak](#-erabilitako-teknologiak)
- [Datu-basea](#-datu-basea)
- [Erabiltzaileak eta Baimenak](#-erabiltzaileak-eta-baimenak)
- [Garapena](#-garapena)
- [Arazoak Konpontzea](#-arazoak-konpontzea)
- [Lizentzia](#-lizentzia)

## 🎯 Proiektuaren Deskribapena

OtherProteins kirol osagarrien, proteinen, kreatinaren, pre-entrenamendu produktuen eta barriten salmentan espezializatutako e-commerce plataforma da. Aplikazioak erabiltzaileei aukera ematen die:

- Produktuak kategorien arabera bilatu eta arakatu
- Produktuak erosketa saskira gehitu
- Eskaerak egin eta haien historiala kudeatu
- PDF formatuan fakturak deskargatu
- Erabiltzaile profila kudeatu

Administratzaileek kontrol panel bat dute:

- Produktuen stock-a aldatzeko
- Produktuen izenak eta xehetasunak editatzeko
- Bezero guztien eskaera guztiak ikusteko
- Bezero presentzialentzat fakturak sortzeko

## ✨ Ezaugarriak

### Bezeroentzat
- **Produktuen Katalogoa**: Produktuen ikuspegia irudiekin, deskribapenekin, prezioekin eta eskuragarritasunarekin
- **Erosketa Saskia**: Erosketa amaitzeko produktuen kudeaketa
- **Eskaera Sistema**: Eskaerak sortu eta jarraitu egoera desberdinekin
- **Profil Kudeaketa**: Informazio pertsonala eguneratzea (izena, abizenak, email, telefonoa)
- **PDF Fakturak**: Eskaera bakoitzarentzat faktura/txartelak PDF formatuan deskargatzea
- **Eskaeren Historia**: Egindako eskaera guztiak ikustea
- **Eskaerak Bertan Behera Uztea**: Lehenengo 24 orduetan eskaerak bertan behera uzteko aukera

### Administratzaileentzat
- **Administrazioa Panela**: `admin@gmail.com` erabiltzailearekin sarbide esklusiboa
- **Stock Kudeaketa**: Produktuen stock-a modu intuitiboan aldatzea
- **Produktuen Edizioa**: Produktuen izenak eta xehetasunak aldatzea
- **Eskaera Ikuspegi Osoa**: Bezero guztien eskaera guztiak ikusteko sarbidea
- **Faktura Sortzea**: Bezero presentzialentzat datu pertsonalizatuekin fakturak sortzea
- **Eskaera Automatikoak**: Administratzailearen eskaerak automatikoki "pagado" egoeran sortzen dira

## 💻 Sistema Eskakizunak

### Python Bertsioa
- **Python 3.8 edo goragokoa** (gomendatua: Python 3.9, 3.10, 3.11 edo 3.12)

### Sistema Eragileak
Aplikazioa honako sistema eragileetan dabil:
- **Windows** (Windows 10/11 edo goragokoa)
- **Linux** (Ubuntu 20.04+, Debian 10+, Fedora 33+, etab.)
- **macOS** (macOS 10.15 Catalina edo goragokoa)

### Sistema Menpekotasunak
- **SQLite3** (Python-en berez barne dago)
- **pip** (Python paketeen kudeatzailea)

## 🚀 Instalazioa

### 1. Errepisitorioa Klonatzea

```bash
git clone https://github.com/Zubiarka8/OtherProteins.git
cd OtherProteins
```

### 2. Ingurune Birtuala Sortzea

#### Windows (PowerShell)
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

#### Windows (CMD)
```cmd
python -m venv .venv
.venv\Scripts\activate.bat
```

#### Linux/macOS
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Menpekotasunak Instalatzea

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

Honek instalatuko du:
- **Flask**: Web framework-a
- **reportlab**: PDF fakturak sortzeko

## ⚙️ Konfigurazioa

### Datu-basea Hasieratzea

Datu-basea automatikoki hasieratzen da aplikazioa lehen aldiz exekutatzean. Berriro hasieratu behar baduzu:

```bash
python database.py
```

Honek sortuko du:
- Beharrezko taulak (erabiltzaileak, produktuak, kategoriak, eskaerak, saskia)
- Lehenetsitako administratzaile erabiltzailea:
  - **Email**: `admin@gmail.com`
  - **Pasahitza**: `admin123`
- Adibide datuak (produktuak eta kategoriak)

### Segurtasun Konfigurazioa

⚠️ **GARRANTZITSUA**: Produkzioan zabaldu aurretik, aldatu sekretu gakoa `app.py` fitxategian:

```python
app.config['SECRET_KEY'] = 'zure_sekretu_gako_oso_segurua_hemen'
```

## 🎮 Erabilera

### Aplikazioa Exekutatzen

#### Windows
```powershell
# Ziurtatu ingurune birtuala aktibatuta dagoela
python app.py
```

#### Linux/macOS
```bash
# Ziurtatu ingurune birtuala aktibatuta dagoela
python3 app.py
```

Edo Flask zuzenean erabiliz:

```bash
flask run
```

### Aplikazioan Sartzea

Abiarazi ondoren, aplikazioa honako helbidean eskuragarri dago:
- **URL**: `http://localhost:5000` edo `http://127.0.0.1:5000`
- Ireki zure web nabigatzailea eta joan goiko URL-era

### Lehenetsitako Erabiltzaileak

#### Administratzailea
- **Email**: `admin@gmail.com`
- **Pasahitza**: `admin123`
- **Baimenak**: Administrazio panel guztirako sarbidea

#### Erabiltzaile Arrunta
Erabiltzaile berri bat sor dezakezu erregistro orritik (`/register`)

## 📁 Proiektuaren Egitura

```
OtherProteins/
│
├── app.py                 # Flask aplikazio nagusia
├── database.py            # Datu-basearen konfigurazioa eta eskema
├── db_utils.py           # Datu-base eragiketetarako utilitateak
├── products.py           # Produktuen biderako Blueprint
├── requirements.txt      # Proiektuaren menpekotasunak
├── README.md            # Fitxategi hau
│
├── templates/           # HTML plantillak (Jinja2)
│   ├── layout.html      # Oinarrizko plantilla
│   ├── index.html       # Orri nagusia
│   ├── products.html    # Produktuen zerrenda
│   ├── product_detail.html  # Produktuaren xehetasunak
│   ├── cart.html        # Erosketa saskia
│   ├── checkout.html    # Erosketa prozesua
│   ├── orders.html      # Eskaeren historia
│   ├── order_detail.html # Eskaeraren xehetasunak
│   ├── login.html       # Saioa hasi
│   ├── register.html    # Erabiltzaile erregistroa
│   ├── admin_stock.html # Stock administrazio panela
│   ├── admin_complete_profile.html # Administratzaile faktura formularioa
│   └── ...
│
├── static/              # Estatiko fitxategiak
│   ├── css/
│   │   └── style.css   # CSS estiloak
│   └── js/
│       └── main.js     # Bezeroaren JavaScript
│
├── otherproteins.db    # SQLite datu-basea (automatikoki sortzen da)
└── error.log          # Errore log fitxategia
```

## 🛠️ Erabilitako Teknologiak

- **Backend**:
  - **Flask 2.x+**: Web framework arina eta malgua
  - **SQLite3**: Datu-base erlazional txertatua
  - **ReportLab**: PDF dokumentuak sortzeko

- **Frontend**:
  - **HTML5**: Orrien egitura
  - **CSS3**: Estiloak eta diseinu erantzunkorra
  - **JavaScript**: Bezeroaren interaktibitatea
  - **Bootstrap 5**: Diseinu erantzunkorrako CSS framework
  - **Bootstrap Icons**: Ikonoak

- **Hizkuntza**:
  - **Python 3.8+**: Programazio hizkuntza nagusia

## 🗄️ Datu-basea

### Oinarrizko Eskema

- **erabiltzaileak**: Erabiltzaileen informazioa
- **produktuak**: Produktuen katalogoa
- **kategoriak**: Produktuen kategoriak
- **eskaerak**: Egindako eskaerak
- **eskaera_elementuak**: Eskaera bakoitzeko produktuak
- **saskia**: Erabiltzaile bakoitzaren saskiko produktuak

### Eskaera Egoerak

- `prozesatzen`: Prozesatzen
- `pagado`: Ordainduta
- `bidalita`: Bidalita
- `bukatuta`: Bukatuta
- `bertan_behera`: Bertan behera utzita

## 👥 Erabiltzaileak eta Baimenak

### Erabiltzaile Arrunta
- Produktuak ikustea
- Saskira gehitu
- Eskaerak egitea
- Bere eskaeren historia ikustea
- Eskaerak bertan behera uztea (24 ordu barru)
- Bere eskaeren fakturak deskargatzea

### Administratzaile Erabiltzailea (`admin@gmail.com`)
- Erabiltzaile arrunten funtzio guztiak
- Produktuen stock-a aldatzea
- Produktuen izenak editatzeko
- Bezero guztien eskaera guztiak ikustea
- Bezero presentzialentzat fakturak sortzea
- Eskaerak automatikoki "pagado" egoeran sortzen dira

## 🔧 Garapena

### Garapen Modua

Garapen moduan exekutatzeko kargaketa automatikorekin:

```bash
# Windows
$env:FLASK_ENV="development"; python app.py

# Linux/macOS
export FLASK_ENV=development
python3 app.py
```

### Debugging

Erroreak honakoetan erregistratzen dira:
- **Kontsola**: Irteera estandarra
- **Fitxategia**: `error.log`

### Produktu Berriak Gehitzea

Produktuak honako moduetan gehi daitezke:
1. Datu-basean zuzenean
2. Administrazio panelaren bidez (izenak editatu)
3. `database.py` aldatuz eta `python database.py` exekutatuz

## 🐛 Arazoak Konpontzea

### Errorea: "ModuleNotFoundError: No module named 'flask'"

**Konponbidea**: Ziurtatu ingurune birtuala aktibatuta dagoela eta menpekotasunak instalatuta daudela:
```bash
source .venv/bin/activate  # Linux/macOS
# edo
.venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

### Errorea: "Database is locked"

**Konponbidea**: Itxi aplikazioaren beste instantziak datu-basea erabiliz egon daitezkeenak.

### Errorea: "No such table: produktuak"

**Konponbidea**: Hasieratu datu-basea:
```bash
python database.py
```

### Aplikazioa ez da abiarazten 5000 portuan

**Konponbidea**: Egiaztatu portua ez dagoela erabilita. Portua alda dezakezu `app.py`-n:
```python
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)  # Aldatu 5001 nahi duzun portura
```

### PDF-ekin Arazoak

**Konponbidea**: Ziurtatu `reportlab` instalatuta dagoela:
```bash
pip install reportlab
```

## 📝 Ohar Gehigarriak

- Interfazea erabat **euskaran** dago
- Prezioak **eurotan (€)** daude
- Bidalketa **doan** da 50€ baino gehiagoko eskaeretan
- Eskaerak **lehenengo 24 orduetan** bertan behera utzi daitezke
- PDF fakturak eskaeraren informazio osoarekin sortzen dira

## 📄 Lizentzia

Proiektu hau pribatua da. Eskubide guztiak erreserbatuta.

## 👨‍💻 Egilea

OtherProteins - Kirol osagarrien eta nutrizio produktuen denda.

## 🔗 Errepisitorioa

Proiektuaren GitHub errepisitorioa: [https://github.com/Zubiarka8/OtherProteins.git](https://github.com/Zubiarka8/OtherProteins.git)

---

**Bertsioa**: 1.0.0  
**Azken eguneratzea**: 2024
