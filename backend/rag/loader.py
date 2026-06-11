from langchain_community.document_loaders import TextLoader,JSONLoader,UnstructuredMarkdownLoader
from langchain_core.documents import Document

def load_documents(data_dir:str="rag/data")->list[Document]:
    doc=[]
    import glob
    # 把MarkDown文件加载到doc文档里面
    for md_path in glob.glob(f"{data_dir}/*.md"):
        loader = UnstructuredMarkdownLoader(md_path)
        doc.append(loader.load())


    for json_path in glob.glob(f"{data_dir}/*.json"):
        loader = JSONLoader(
            file_path=json_path,
            jq_schema=".[].description",
            text_content=False
        )
        doc.append(loader.load())

    for tex_path in glob.glob(f"{data_dir}/*.txt"):
        loader = TextLoader(tex_path,encoding="utf-8")
        doc.append(loader.load())


    return doc
