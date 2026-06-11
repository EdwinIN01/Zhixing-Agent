from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from utils.config_handler import chroma_config

def split_documents(docs:list[Document]) -> list[Document]:
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chroma_config["chunk_size"],
        chunk_overlap=chroma_config["chunk_overlap"],
        separators=chroma_config["separators"],
        length_function=len
    )

    return text_splitter.split_documents(docs)