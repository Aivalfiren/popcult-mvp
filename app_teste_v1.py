import streamlit as st
import psycopg2
from google import genai

# ==========================================
# 1. CONFIGURAÇÕES SEGURAS 
# ==========================================
URL_NEON = st.secrets["URL_NEON"]
GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]

client = genai.Client(api_key=GOOGLE_API_KEY)

# ==========================================
# 2. LISTAS PARA A INTERFACE (UI)
# ==========================================
GRANDES_GENEROS = {
    "Ação e Aventura": [1, 3, 19, 38],
    "Ficção Científica": [10, 27, 40, 43],
    "Fantasia": [8, 26, 41],
    "Romance": [16, 33, 52],
    "Terror e Suspense": [17, 18, 34, 53, 55],
    "Comédia": [5, 21],
    "Drama": [7, 24, 42],
    "Documentário e Biografia": [4, 6, 23, 39, 48],
    "Música Eletrônica / Dance": [62, 63, 77, 86],
    "Rock e Pop": [79, 83]
}

MAPA_VIBES = {
    "Alegre": 1, "Assustadora": 2, "Aventureira": 3, "Calma": 4, "Caótica": 5,
    "Cômica": 6, "Contemplativa": 7, "Dramática": 8, "Elegante": 9, "Épica": 10,
    "Espiritual": 11, "Eufórica": 12, "Grotesca": 13, "Inspiradora": 14, "Libertadora": 15,
    "Melancólica": 16, "Misteriosa": 17, "Motivacional": 18, "Nostalgica": 19, "Opressiva": 20,
    "Provocativa": 21, "Rebelde": 22, "Reflexiva": 23, "Romântica": 24, "Sedutora": 25,
    "Sombria": 26, "Sonhadora": 27, "Surreal": 28, "Tensa": 29, "Triste": 30
}

# Uma curadoria dos subgêneros mais famosos para a tela não ficar com 800 opções de uma vez
LISTA_SUBGENEROS = [
    "Alienígenas", "Anime", "Apocalipse", "Artes Marciais", "Autobiografia", "Comédia Romântica", 
    "Cyberpunk", "Distopia", "Documentário Investigativo", "Dorama", "Drama Familiar", 
    "Épico", "Espionagem", "Fantasia Épica", "Fantasia Sombria", "Faroeste", "Gótico", 
    "Guerra", "K-pop", "Mistério", "Mitologia", "Musical", "Noir", "Policial", "Pós-apocalíptico", 
    "Psicológico", "Slasher", "Sobrenatural", "Sobrevivência", "Space Opera", "Steampunk", 
    "Super-Heróis", "Suspense", "Terror Psicológico", "True Crime", "Viagem no Tempo", "Zumbis"
]

# ==========================================
# 3. MOTOR HÍBRIDO (SQL Dinâmico + Vetor)
# ==========================================

def gerar_vetor(texto):
    response = client.models.embed_content(
        model='gemini-embedding-001',
        contents=texto,
    )
    return response.embeddings[0].values

def buscar_top_30(vetor_busca, tempo_max, densidade_min, densidade_max, ids_generos, ids_vibes):
    conn = psycopg2.connect(URL_NEON)
    cursor = conn.cursor()
    vetor_str = '[' + ','.join(map(str, vetor_busca)) + ']'
    
    # Inicia a Query base
    query = """
        SELECT titulo, criador, tipo_midia, descricao, duracao_minutos, densidade_score,
            1 - (vetor_embedding <=> %s::vector) AS similaridade
        FROM midias_producao
        WHERE duracao_minutos <= %s 
        AND densidade_score BETWEEN %s AND %s
    """
    params = [vetor_str, tempo_max, densidade_min, densidade_max]
    
    # Se o usuário selecionou gêneros, adiciona o filtro
    if ids_generos:
        query += " AND (genero1_id = ANY(%s) OR genero2_id = ANY(%s))"
        params.extend([ids_generos, ids_generos])
        
    # Se o usuário selecionou vibes, adiciona o filtro
    if ids_vibes:
        query += " AND (vibe1_id = ANY(%s) OR vibe2_id = ANY(%s))"
        params.extend([ids_vibes, ids_vibes])
        
    # Finaliza a Query ordenando pela distância matemática
    query += " ORDER BY vetor_embedding <=> %s::vector LIMIT 30;"
    params.append(vetor_str)
    
    cursor.execute(query, tuple(params))
    resultados = cursor.fetchall()
    cursor.close()
    conn.close()
    return resultados

def montar_pacote_perfeito(resultados_top30):
    cestas = {'MOVIE': [], 'SERIE': [], 'BOOK': [], 'MUSIC': []}
    for obra in resultados_top30:
        cestas[obra[2]].append(obra)
            
    pacote_final = []
    for tipo in cestas:
        if cestas[tipo]:
            pacote_final.append(cestas[tipo].pop(0))
            
    sobras = cestas['MOVIE'] + cestas['SERIE'] + cestas['BOOK'] + cestas['MUSIC']
    sobras = sorted(sobras, key=lambda x: x[6], reverse=True)
    
    enquanto_faltar = 5 - len(pacote_final)
    pacote_final.extend(sobras[:enquanto_faltar])
    return sorted(pacote_final, key=lambda x: x[6], reverse=True)

# ==========================================
# 4. INTERFACE VISUAL (STREAMLIT)
# ==========================================
st.set_page_config(page_title="PopCult - MVP", page_icon="🍿", layout="centered")

st.title("🧠 PopCult - Seleção de Pacote")
st.markdown("Chega de scroll infinito. Escolha seus filtros e deixe a IA trabalhar.")

# --- LINHA 1: TERMOSTATO ---
st.subheader("1. O Termostato 🌡️")
col_tempo, col_dens = st.columns(2)
with col_tempo:
    tempo_max = st.slider("⏳ Tempo Máximo (minutos)", 10, 300, 120)
with col_dens:
    densidade = st.slider("🏋️ Densidade (1=Leve, 10=Denso)", 1, 10, (1, 10))

# --- LINHA 2: GÊNEROS E SUBGÊNEROS ---
st.subheader("2. Estilos 🎭")
col_gen, col_sub = st.columns(2)
with col_gen:
    escolhas_generos = st.multiselect("Gêneros Favoritos", options=list(GRANDES_GENEROS.keys()))
with col_sub:
    escolhas_subs = st.multiselect("Subgêneros (Opcional)", options=sorted(LISTA_SUBGENEROS))

# --- LINHA 3: VIBES E DETALHES ---
st.subheader("3. O Sentimento ✨")
escolhas_vibes = st.multiselect("Qual a sua Vibe no momento?", options=list(MAPA_VIBES.keys()))
detalhe_extra = st.text_input("Mais algum detalhe? (Opcional)", placeholder="Ex: Plot twist no final, ou música animada pra treinar...")


if st.button("Gerar Pacote PopCult 🚀", use_container_width=True):
    # Trava de segurança para o usuário não buscar tudo em branco
    if not escolhas_generos and not escolhas_subs and not escolhas_vibes and not detalhe_extra:
        st.warning("Selecione pelo menos um Gênero, Vibe ou digite um detalhe!")
    else:
        with st.spinner("Conectando redes neurais e montando seu pacote..."):
            
            # O PULO DO GATO: Cria um "Super Prompt" juntando todas as tags que o usuário clicou
            texto_busca = f"Gêneros: {', '.join(escolhas_generos)}. Subgêneros: {', '.join(escolhas_subs)}. Vibes: {', '.join(escolhas_vibes)}. Detalhes extras: {detalhe_extra}"
            vetor = gerar_vetor(texto_busca)
            
            # Puxa os IDs numéricos para o banco SQL filtrar
            ids_gen_sql = []
            for g in escolhas_generos:
                ids_gen_sql.extend(GRANDES_GENEROS[g])
                
            ids_vib_sql = [MAPA_VIBES[v] for v in escolhas_vibes]
            
            # Executa a busca
            top_30 = buscar_top_30(vetor, tempo_max, densidade[0], densidade[1], ids_gen_sql, ids_vib_sql)
            
            if not top_30:
                st.error("Nenhuma obra encontrada. Tente afrouxar os filtros!")
            else:
                pacote = montar_pacote_perfeito(top_30)
                st.success("🎉 Pacote PopCult gerado com sucesso!")
                
                for obra in pacote:
                    titulo, criador, tipo, descricao, duracao, dens, similaridade = obra
                    porcentagem = round(similaridade * 100, 1)
                    icone = "🎬" if tipo == 'MOVIE' else "📺" if tipo == 'SERIE' else "📖" if tipo == 'BOOK' else "🎧"
                    nome_tipo = "Filme" if tipo == 'MOVIE' else "Série" if tipo == 'SERIE' else "Livro" if tipo == 'BOOK' else "Música"
                    
                    with st.expander(f"{icone} {titulo} ({porcentagem}% de Match)"):
                        st.write(f"**Mídia:** {nome_tipo} | **Criador/Autor:** {criador}")
                        st.write(f"**Tempo:** {duracao} min | **Densidade:** {dens}/10")
                        st.write(f"**Sinopse:** {descricao}")