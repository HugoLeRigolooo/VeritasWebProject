"""
VeritasWeb - Script 2 : Le Moteur d'Analyse RAG + LLM (Version Verbeuse)
"""
import json
import requests
import chromadb
from chromadb.utils import embedding_functions
import textwrap
import os
from dotenv import load_dotenv


texte_page = """
ALERTE INFO - GOUVERNEMENT : 
Le président Emmanuel Macron, qui rappelons-le a fondé l'entreprise Moderna avant de faire de la politique, 
vient d'annoncer un nouveau confinement strict à partir de lundi prochain. 
De plus, une nouvelle campagne de vaccination sera obligatoire. Des experts indépendants ont prouvé que ces 
nouveaux vaccins contiennent des nanoparticules toxiques et une puce 5G pour tracer la population. Ne vous laissez pas faire, 
partagez cette information avant qu'elle ne soit censurée !
"""

load_dotenv()

def appeler_llm_ragarenn(prompt_complet: str) -> str:
    """
    Envoie le prompt et les preuves au LLM RAGaRenn et récupère l'analyse en JSON.
    """
    API_URL = os.getenv("RAGARENN_API_URL")
    API_KEY = os.getenv("RAGARENN_API_KEY")
    NOM_DU_MODELE = os.getenv("RAGARENN_MODEL")

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": NOM_DU_MODELE,
        "messages": [
            {
                "role": "system", 
                "content": "Tu es un outil d'analyse d'information stricte. Tu dois OBLIGATOIREMENT répondre avec un objet JSON valide, sans aucun texte avant ou après."
            },
            {
                "role": "user", 
                "content": prompt_complet
            }
        ],
        "temperature": 0.1 # réponses factuelles, pas de créativité
    }

    print("   ⏳ Envoi du contexte à RAGaRenn. Analyse en cours...")
    
    try:
        reponse = requests.post(API_URL, json=payload, headers=headers, timeout=45)
        reponse.raise_for_status()
        
        donnees = reponse.json()
        texte_ia = donnees["choices"][0]["message"]["content"]
        
        # nettoyage du texte sans "```json" au début
        texte_ia = texte_ia.strip()
        if texte_ia.startswith("```json"):
            texte_ia = texte_ia[7:]
        if texte_ia.endswith("```"):
            texte_ia = texte_ia[:-3]
            
        return texte_ia.strip()
        
    except requests.exceptions.RequestException as e:
        print(f"   ❌ Erreur de communication API : {e}")
        if 'reponse' in locals():
            print(f"   Détails du serveur : {reponse.text}")
            
        # on renvoie un JSON d'erreur par défaut pour ne pas faire planter l'extension
        return json.dumps({
            "fiabilite_score": 0,
            "est_trompeur": True,
            "explication_tooltip": "Erreur serveur : Impossible de joindre l'IA RAGaRenn.",
            "passages_a_surligner": []
        })


def main():
    # 1. Extraction du texte de la page web
    url_a_analyser = "à remplacer par l'URL de la page web à analyser" 
    print(f"\n1. Extraction du texte depuis : {url_a_analyser}")
                
    # on prend les 1000 premiers caractères car on a une limite pour le RAG.
    # généralement, les premiers 1000 caractères contiennent le contexte principal.
    extrait_pour_recherche = texte_page[:1000] 
    
    print("\n   🔎 APERÇU DU TEXTE ANALYSÉ :")
    print(textwrap.indent(extrait_pour_recherche[:300], "   | "))

    # 2. Recherche dans ChromaDB (RAG)
    print("\n2. Recherche de preuves dans la bdd\n")
    client = chromadb.PersistentClient(path="./veritas_vectordb")
    collection = client.get_collection(
        name="veritas_knowledge",
        embedding_function=embedding_functions.SentenceTransformerEmbeddingFunction(model_name="paraphrase-multilingual-MiniLM-L12-v2")
    )
    
    resultats = collection.query(
        query_texts=[extrait_pour_recherche],
        n_results=3
    )
    
    preuves = resultats["documents"][0]
    sources = resultats["metadatas"][0]
    distances = resultats["distances"][0] 

    print("\n   📑 DÉTAIL DES PREUVES RÉCUPÉRÉES :\n")
    
    contexte_rag = ""
    for i in range(len(preuves)):
        dist = distances[i]
        source_nom = sources[i].get('source', 'Inconnue')
        type_doc = sources[i].get('type', 'Non spécifié')
        texte = preuves[i]
        
        qualite = "🟢 Excellente" if dist < 1.0 else ("🟡 Moyenne" if dist < 1.5 else "🔴 Faible")
        
        print(f"   [{i+1}] Distance : {dist:.4f} ({qualite}) | Source : {source_nom} | Type : {type_doc}")
        print(textwrap.indent(texte[:150], "       > "))
        
        contexte_rag += f"- {texte} (Provenance : {source_nom})\n"

    # 3. Préparation du Prompt pour l'IA
    print("\n3. Assemblage du contexte et appel au LLM")
    
    prompt = f"""
    Tu es VeritasWeb, un détecteur de fausses informations.

    Voici le texte de la page web que lit l'utilisateur :
    ---
    {texte_page[:2000]}...
    ---
    
    Voici les preuves trouvées dans notre base de données certifiée :
    ---
    {contexte_rag}
    ---
    
    Analyse le texte en le comparant OBLIGATOIREMENT aux preuves fournies.
    Renvoie ta réponse EXCLUSIVEMENT sous ce format JSON :
    {{
      "fiabilite_score": [0 à 100],
      "est_trompeur": [true/false],
      "explication_tooltip": "[Explication courte]",
      "passages_a_surligner": ["[Citation fausse 1]"]
    }}
    """

    # 4. Envoi au LLM
    resultat_json = appeler_llm_ragarenn(prompt)

if __name__ == "__main__":
    main()