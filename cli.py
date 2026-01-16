"""
Legal RAG CLI - Command Line Interface
"""

import os
import json
import click
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown
from rich.progress import Progress, SpinnerColumn, TextColumn
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

console = Console()

# Paths
BASE_DIR = Path(__file__).parent.resolve()
DOCUMENTS_DIR = BASE_DIR / "documents"
DATA_DIR = BASE_DIR / "data"
INDEX_DIR = DATA_DIR / "indices"
PARSED_DIR = DATA_DIR / "parsed"


@click.group()
@click.version_option(version="1.0.0")
def cli():
    """Legal RAG CLI - Hierarchical Legal Document Search System"""
    pass


@cli.command()
@click.option("--documents-dir", "-d", default=str(DOCUMENTS_DIR), help="Directory containing PDF documents")
@click.option("--output-dir", "-o", default=str(PARSED_DIR), help="Output directory for parsed JSON")
def parse(documents_dir: str, output_dir: str):
    """Parse PDF documents into structured JSON format."""
    from src.pdf_parser import parse_all_documents
    from src.sop_parser import parse_sop, SOPDocument
    
    documents_path = Path(documents_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    console.print(Panel.fit(
        "[bold blue]Legal Document Parser[/bold blue]\n"
        f"Documents: {documents_path}\n"
        f"Output: {output_path}",
        title="📄 Parsing Documents"
    ))
    
    # Parse all legal documents (BNS, BNSS, BSA)
    documents = parse_all_documents(documents_path)
    
    # Parse SOP documents separately (Tier-1 feature)
    sop_docs = []
    for pdf_file in documents_path.glob("*.pdf"):
        if "SOP" in pdf_file.name.upper():
            console.print(f"[blue]Parsing SOP:[/blue] {pdf_file.name}")
            try:
                sop = parse_sop(pdf_file)
                sop_docs.append(sop)
                console.print(f"  → Found {len(sop.blocks)} procedural blocks")
            except Exception as e:
                console.print(f"[yellow]Warning: Could not parse SOP {pdf_file.name}: {e}[/yellow]")
    
    if not documents and not sop_docs:
        console.print("[red]No documents were parsed![/red]")
        return
    
    # Save each legal document
    for doc in documents:
        output_file = output_path / f"{doc.doc_id}.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(doc.to_dict(), f, ensure_ascii=False, indent=2)
        console.print(f"[green]✓[/green] Saved: {output_file.name}")
    
    # Save each SOP document
    for sop in sop_docs:
        output_file = output_path / f"{sop.doc_id}.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(sop.to_dict(), f, ensure_ascii=False, indent=2)
        console.print(f"[green]✓[/green] Saved: {output_file.name} (SOP)")
    
    # Print summary for legal documents
    if documents:
        table = Table(title="Legal Documents Summary")
        table.add_column("Document", style="cyan")
        table.add_column("Chapters", justify="right")
        table.add_column("Sections", justify="right")
        table.add_column("Subsections", justify="right")
        table.add_column("Pages", justify="right")
        
        for doc in documents:
            total_sections = sum(len(c.sections) for c in doc.chapters)
            total_subsections = sum(
                len(s.subsections) 
                for c in doc.chapters 
                for s in c.sections
            )
            table.add_row(
                doc.short_name,
                str(len(doc.chapters)),
                str(total_sections),
                str(total_subsections),
                str(doc.total_pages)
            )
        
        console.print(table)
    
    # Print summary for SOP documents
    if sop_docs:
        sop_table = Table(title="SOP Documents Summary")
        sop_table.add_column("Document", style="green")
        sop_table.add_column("Blocks", justify="right")
        sop_table.add_column("Case Types", justify="left")
        sop_table.add_column("Pages", justify="right")
        
        for sop in sop_docs:
            sop_table.add_row(
                sop.short_name,
                str(len(sop.blocks)),
                ", ".join(sop.case_types),
                str(sop.total_pages)
            )
        
        console.print(sop_table)


@cli.command()
@click.option("--parsed-dir", "-p", default=str(PARSED_DIR), help="Directory with parsed JSON documents")
@click.option("--index-dir", "-i", default=str(INDEX_DIR), help="Output directory for indices")
@click.option("--model", "-m", default="sentence-transformers/all-MiniLM-L6-v2", help="Embedding model name")
def index(parsed_dir: str, index_dir: str, model: str):
    """Generate embeddings and build vector indices."""
    from src.models import LegalDocument
    from src.sop_parser import SOPDocument
    from src.embedder import HierarchicalEmbedder
    from src.vector_store import MultiLevelVectorStore
    
    parsed_path = Path(parsed_dir)
    index_path = Path(index_dir)
    index_path.mkdir(parents=True, exist_ok=True)
    
    console.print(Panel.fit(
        "[bold blue]Building Vector Indices[/bold blue]\n"
        f"Model: {model}\n"
        f"Parsed: {parsed_path}\n"
        f"Indices: {index_path}",
        title="🔍 Indexing Documents"
    ))
    
    # Load parsed documents
    json_files = list(parsed_path.glob("*.json"))
    if not json_files:
        console.print("[red]No parsed documents found! Run 'parse' first.[/red]")
        return
    
    documents = []
    sop_docs = []
    
    for json_file in json_files:
        with open(json_file, "r", encoding="utf-8") as f:
            doc_dict = json.load(f)
            
            # Check if it's an SOP document
            if doc_dict.get("doc_type") == "SOP":
                sop_docs.append(SOPDocument.from_dict(doc_dict))
                console.print(f"[green]Loaded SOP:[/green] {json_file.name}")
            else:
                documents.append(LegalDocument.from_dict(doc_dict))
                console.print(f"[blue]Loaded:[/blue] {json_file.name}")
    
    # Initialize embedder
    embedder = HierarchicalEmbedder(model_name=model)
    
    # Generate embeddings for all legal documents
    for doc in documents:
        embedder.embed_document(doc)
    
    # Generate embeddings for SOP documents
    for sop in sop_docs:
        console.print(f"[green]Embedding SOP:[/green] {sop.short_name}")
        embedder.embed_sop_document(sop)
    
    # Build vector store
    assert embedder.embedding_dim is not None, "Embedding dimension not initialized"
    store = MultiLevelVectorStore(embedding_dim=embedder.embedding_dim)
    
    for doc in documents:
        store.add_document(doc)
    
    # Add SOP documents to store
    for sop in sop_docs:
        store.add_sop_document(sop)
    
    # Build BM25 indices
    store.build_bm25_indices()
    
    # Save indices
    store.save(index_path)
    
    # Print stats
    stats = store.get_stats()
    table = Table(title="Index Statistics")
    table.add_column("Level", style="cyan")
    table.add_column("Count", justify="right")
    
    for level, count in stats.items():
        if level != "embedding_dim":
            table.add_row(level.capitalize(), str(count))
    
    table.add_row("Embedding Dim", str(stats["embedding_dim"]))
    console.print(table)
    
    console.print(f"\n[green]✓ Indices saved to {index_path}[/green]")


@cli.command()
@click.argument("question")
@click.option("--index-dir", "-i", default=str(INDEX_DIR), help="Directory with vector indices")
@click.option("--model", "-m", default="sentence-transformers/all-MiniLM-L6-v2", help="Embedding model")
@click.option("--top-k", "-k", default=5, help="Number of results to return")
@click.option("--no-llm", is_flag=True, help="Skip LLM answer generation")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed retrieval results")
@click.option("--show-context", is_flag=True, help="Show raw context sent to LLM")
def query(question: str, index_dir: str, model: str, top_k: int, no_llm: bool, verbose: bool, show_context: bool):
    """Query the legal document database."""
    from src.embedder import HierarchicalEmbedder
    from src.vector_store import MultiLevelVectorStore
    from src.retriever import HierarchicalRetriever, RetrievalConfig, LegalRAG
    
    index_path = Path(index_dir)
    
    if not index_path.exists():
        console.print("[red]Index not found! Run 'index' first.[/red]")
        return
    
    # Load components
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("Loading model...", total=None)
        embedder = HierarchicalEmbedder(model_name=model)
        
        progress.update(task, description="Loading indices...")
        assert embedder.embedding_dim is not None, "Embedding dimension not initialized"
        store = MultiLevelVectorStore(embedding_dim=embedder.embedding_dim)
        store.load(index_path)
    
    # Configure retriever
    config = RetrievalConfig(
        top_k_subsections=top_k,
        use_hybrid_search=True
        # use_hierarchical_filtering defaults to False for better recall
    )
    
    retriever = HierarchicalRetriever(store, embedder, config)
    
    # Initialize Gemini LLM client if needed
    llm_client = None
    if not no_llm:
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key:
            try:
                from google import genai
                llm_client = genai.Client(api_key=api_key)
            except Exception as e:
                console.print(f"[yellow]Warning: Could not initialize Gemini client: {e}[/yellow]")
    
    rag = LegalRAG(retriever, llm_client)
    
    # Execute query
    console.print(Panel.fit(
        f"[bold]{question}[/bold]",
        title="❓ Question"
    ))
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("Searching...", total=None)
        result = rag.query(question, generate_answer=not no_llm and llm_client is not None)
    
    # Display results
    if verbose:
        # Show retrieval stages
        if result["retrieval"]["documents"]:
            console.print("\n[bold cyan]📚 Documents Found:[/bold cyan]")
            for doc in result["retrieval"]["documents"]:
                console.print(f"  • {doc['citation']} (score: {doc['score']})")
        
        if result["retrieval"]["chapters"]:
            console.print("\n[bold cyan]📖 Relevant Chapters:[/bold cyan]")
            for ch in result["retrieval"]["chapters"]:
                console.print(f"  • {ch['citation']} (score: {ch['score']})")
        
        if result["retrieval"]["sections"]:
            console.print("\n[bold cyan]📑 Relevant Sections:[/bold cyan]")
            for sec in result["retrieval"]["sections"]:
                console.print(f"  • {sec['citation']} (score: {sec['score']})")
    
    # Show SOP blocks if present (Tier-1 feature)
    if result["retrieval"].get("sop_blocks"):
        console.print("\n[bold green]📘 SOP Procedural Guidance Found:[/bold green]")
        sop_table = Table(show_header=True, header_style="bold green")
        sop_table.add_column("Stage", style="yellow", width=20)
        sop_table.add_column("Guidance", width=60)
        sop_table.add_column("Time", width=12)
        
        for sop in result["retrieval"]["sop_blocks"][:5]:
            stage = sop["metadata"].get("procedural_stage", "").replace("_", " ").title()
            time_limit = sop["metadata"].get("time_limit", "-")
            sop_table.add_row(
                stage,
                sop["text"][:200] + "..." if len(sop["text"]) > 200 else sop["text"],
                time_limit
            )
        
        console.print(sop_table)
    
    # Show subsection results
    console.print("\n[bold cyan]📋 Legal Provisions Found:[/bold cyan]")
    
    table = Table(show_header=True, header_style="bold")
    table.add_column("Source", style="cyan", width=35)
    table.add_column("Text", width=60)
    table.add_column("Score", justify="right", width=8)
    
    for sub in result["retrieval"]["subsections"][:top_k]:
        # Add source type indicator
        source_type = sub.get("source_type", "📄")
        citation = f"{source_type} {sub['citation']}"
        table.add_row(
            citation,
            sub["text"][:180] + "..." if len(sub["text"]) > 180 else sub["text"],
            f"{sub['score']:.3f}"
        )
    
    console.print(table)
    
    # Show query intent info for procedural queries
    if result.get("is_procedural"):
        console.print(f"\n[dim]Query Type: Procedural | Case: {result.get('case_type', 'general')} | Stages: {', '.join(result.get('detected_stages', []))}[/dim]")
    
    # Show citations
    if result["citations"]:
        console.print("\n[bold yellow]📌 Citations:[/bold yellow]")
        for citation in result["citations"][:5]:
            console.print(f"  • {citation}")
    
    # Show context length in verbose mode
    if verbose and result["context"]:
        console.print(f"\n[dim]Context sent to LLM: {len(result['context'])} chars (~{len(result['context'])//4} tokens)[/dim]")
    
    # Show raw context if requested
    if show_context and result["context"]:
        console.print("\n[bold magenta]📝 Raw Context Sent to LLM:[/bold magenta]")
        console.print(Panel(result["context"][:3000] + ("..." if len(result["context"]) > 3000 else ""), 
                           title="Context (first 3000 chars)", border_style="magenta"))
    
    # Show LLM answer
    if result["answer"]:
        console.print(Panel(
            Markdown(result["answer"]),
            title="💡 Answer",
            border_style="green"
        ))
    elif no_llm:
        console.print("\n[dim]LLM answer generation skipped (--no-llm flag)[/dim]")
    elif not llm_client:
        console.print("\n[yellow]Set GEMINI_API_KEY environment variable to enable answer generation[/yellow]")


@cli.command()
@click.option("--index-dir", "-i", default=str(INDEX_DIR), help="Directory with vector indices")
@click.option("--model", "-m", default="sentence-transformers/all-MiniLM-L6-v2", help="Embedding model")
def chat(index_dir: str, model: str):
    """Start an interactive chat session."""
    from src.embedder import HierarchicalEmbedder
    from src.vector_store import MultiLevelVectorStore
    from src.retriever import HierarchicalRetriever, RetrievalConfig, LegalRAG
    
    index_path = Path(index_dir)
    
    if not index_path.exists():
        console.print("[red]Index not found! Run 'index' first.[/red]")
        return
    
    console.print(Panel.fit(
        "[bold blue]Legal RAG Chat[/bold blue]\n"
        "Ask questions about Indian legal documents.\n"
        "Type 'quit' or 'exit' to end the session.",
        title="⚖️ Legal Assistant"
    ))
    
    # Load components
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("Loading system...", total=None)
        embedder = HierarchicalEmbedder(model_name=model)
        
        progress.update(task, description="Loading indices...")
        assert embedder.embedding_dim is not None, "Embedding dimension not initialized"
        store = MultiLevelVectorStore(embedding_dim=embedder.embedding_dim)
        store.load(index_path)
    
    # Print stats
    stats = store.get_stats()
    console.print(f"[dim]Loaded: {stats['documents']} docs, {stats['chapters']} chapters, "
                  f"{stats['sections']} sections, {stats['subsections']} subsections[/dim]\n")
    
    # Configure retriever
    config = RetrievalConfig(
        top_k_subsections=5,
        use_hybrid_search=True
        # use_hierarchical_filtering defaults to False for better recall
    )
    
    retriever = HierarchicalRetriever(store, embedder, config)
    
    # Initialize Gemini LLM client
    llm_client = None
    api_key = os.getenv("GEMINI_API_KEY")
    if api_key:
        try:
            from google import genai
            llm_client = genai.Client(api_key=api_key)
            console.print("[green]✓ Gemini connected - answers will be generated[/green]\n")
        except Exception as e:
            console.print(f"[yellow]Gemini not available: {e}[/yellow]\n")
    else:
        console.print("[yellow]Set GEMINI_API_KEY for AI-generated answers[/yellow]\n")
    
    rag = LegalRAG(retriever, llm_client)
    
    # Chat loop
    while True:
        try:
            question = console.input("[bold cyan]You:[/bold cyan] ").strip()
            
            if not question:
                continue
            
            if question.lower() in ["quit", "exit", "q"]:
                console.print("[dim]Goodbye![/dim]")
                break
            
            # Execute query
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
                transient=True
            ) as progress:
                task = progress.add_task("Thinking...", total=None)
                result = rag.query(question, generate_answer=llm_client is not None)
            
            # Show answer
            if result["answer"]:
                console.print(f"\n[bold green]Assistant:[/bold green]")
                console.print(Markdown(result["answer"]))
            else:
                # Show raw results if no LLM
                console.print(f"\n[bold green]Found {len(result['retrieval']['subsections'])} relevant extracts:[/bold green]")
                for sub in result["retrieval"]["subsections"][:3]:
                    console.print(Panel(
                        sub["text"][:500],
                        title=sub["citation"],
                        border_style="dim"
                    ))
            
            # Show citations
            if result["citations"]:
                console.print(f"\n[dim]Sources: {', '.join(result['citations'][:3])}[/dim]")
            
            console.print()
            
        except KeyboardInterrupt:
            console.print("\n[dim]Goodbye![/dim]")
            break
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")


@cli.command()
@click.option("--index-dir", "-i", default=str(INDEX_DIR), help="Directory with vector indices")
def stats(index_dir: str):
    """Show statistics about the indexed documents."""
    from src.vector_store import MultiLevelVectorStore
    
    index_path = Path(index_dir)
    
    if not index_path.exists():
        console.print("[red]Index not found! Run 'index' first.[/red]")
        return
    
    # We need to know the embedding dim to load
    config_path = index_path / "config.json"
    if config_path.exists():
        with open(config_path) as f:
            config = json.load(f)
            embedding_dim = config["embedding_dim"]
    else:
        embedding_dim = 384  # default
    
    store = MultiLevelVectorStore(embedding_dim=embedding_dim)
    store.load(index_path)
    
    stats = store.get_stats()
    
    console.print(Panel.fit(
        "[bold blue]Index Statistics[/bold blue]",
        title="📊 Stats"
    ))
    
    # Legal documents table
    table = Table(title="Legal Documents")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right")
    
    table.add_row("📚 Documents", str(stats["documents"]))
    table.add_row("📖 Chapters", str(stats["chapters"]))
    table.add_row("📑 Sections", str(stats["sections"]))
    table.add_row("📄 Subsections", str(stats["subsections"]))
    
    console.print(table)
    
    # SOP statistics (Tier-1)
    sop_count = stats.get("sop_blocks", 0)
    if sop_count > 0:
        sop_table = Table(title="SOP Documents (Procedural)")
        sop_table.add_column("Metric", style="green")
        sop_table.add_column("Value", justify="right")
        
        sop_table.add_row("📘 SOP Blocks", str(sop_count))
        
        console.print(sop_table)
    
    # Technical info
    tech_table = Table(title="Technical Info")
    tech_table.add_column("Setting", style="dim")
    tech_table.add_column("Value", justify="right")
    
    tech_table.add_row("Embedding Dimension", str(stats["embedding_dim"]))
    tech_table.add_row("Index Location", str(index_path))
    tech_table.add_row("SOP Support", "✅ Enabled" if sop_count > 0 else "❌ No SOP indexed")
    
    console.print(tech_table)


if __name__ == "__main__":
    cli()
