from langchain_chroma import Chroma
from langchain_core.documents import Document
from backend.model.factory import embed_model
from backend.utils.config_handler import chroma_config

def create_vectorstore(doc:list[Document]):
    vectorstore=Chroma.from_documents(
        documents=doc,
        embedding=embed_model,
        persist_directory=chroma_config["persist_directory"],
    )
    return vectorstore

def  load_vectorstore(doc:list[Document]):
    return Chroma(
        embedding_function=embed_model,
        persist_directory=chroma_config["persist_directory"],
    )

def add_vectorstore(doc:list[Document], vectorstore:Chroma):
    vectorstore.add_documents(documents=doc)