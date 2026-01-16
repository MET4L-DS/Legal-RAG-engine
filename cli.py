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
    from src.evidence_parser import parse_evidence_manual, EvidenceManualDocument
    from src.compensation_parser import parse_compensation_scheme, CompensationSchemeDocument
    
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
    
    # Parse Evidence Manual (Tier-2 feature)
    evidence_docs = []
    for pdf_file in documents_path.glob("*.pdf"):
        name_lower = pdf_file.name.lower()
        if "crime" in name_lower and "scene" in name_lower or "evidence" in name_lower and "manual" in name_lower:
            console.print(f"[cyan]Parsing Evidence Manual:[/cyan] {pdf_file.name}")
            try:
                evidence_doc = parse_evidence_manual(pdf_file)
                evidence_docs.append(evidence_doc)
                console.print(f"  → Found {len(evidence_doc.blocks)} evidence blocks")
            except Exception as e:
                console.print(f"[yellow]Warning: Could not parse Evidence Manual {pdf_file.name}: {e}[/yellow]")
    
    # Parse Compensation Scheme (Tier-2 feature)
    compensation_docs = []
    for pdf_file in documents_path.glob("*.pdf"):
        name_lower = pdf_file.name.lower()
        if "nalsa" in name_lower or "compensation" in name_lower and "scheme" in name_lower:
            # Skip if already parsed as something else
            if any(pdf_file.name == e.source_file for e in evidence_docs if hasattr(e, 'source_file')):
                continue
            console.print(f"[magenta]Parsing Compensation Scheme:[/magenta] {pdf_file.name}")
            try:
                comp_doc = parse_compensation_scheme(pdf_file)
                compensation_docs.append(comp_doc)
                console.print(f"  → Found {len(comp_doc.blocks)} compensation blocks")
            except Exception as e:
                console.print(f"[yellow]Warning: Could not parse Compensation Scheme {pdf_file.name}: {e}[/yellow]")
    
    if not documents and not sop_docs and not evidence_docs and not compensation_docs:
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
    
    # Save each Evidence Manual document
    for evidence_doc in evidence_docs:
        output_file = output_path / f"{evidence_doc.doc_id}.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(evidence_doc.to_dict(), f, ensure_ascii=False, indent=2)
        console.print(f"[green]✓[/green] Saved: {output_file.name} (Evidence Manual)")
    
    # Save each Compensation Scheme document
    for comp_doc in compensation_docs:
        output_file = output_path / f"{comp_doc.doc_id}.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(comp_doc.to_dict(), f, ensure_ascii=False, indent=2)
        console.print(f"[green]✓[/green] Saved: {output_file.name} (Compensation Scheme)")
    
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
        sop_table = Table(title="SOP Documents Summary (Tier-1)")
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
    
    # Print summary for Evidence Manual documents (Tier-2)
    if evidence_docs:
        evidence_table = Table(title="Evidence Manual Summary (Tier-2)")
        evidence_table.add_column("Document", style="cyan")
        evidence_table.add_column("Blocks", justify="right")
        evidence_table.add_column("Evidence Types", justify="left")
        evidence_table.add_column("Pages", justify="right")
        
        for evidence_doc in evidence_docs:
            # Count unique evidence types
            evidence_types = set()
            for block in evidence_doc.blocks:
                evidence_types.update(block.evidence_types)
            
            evidence_table.add_row(
                evidence_doc.short_name,
                str(len(evidence_doc.blocks)),
                ", ".join(sorted(t.value for t in list(evidence_types)[:3])) + ("..." if len(evidence_types) > 3 else ""),
                str(evidence_doc.total_pages)
            )
        
        console.print(evidence_table)
    
    # Print summary for Compensation Scheme documents (Tier-2)
    if compensation_docs:
        comp_table = Table(title="Compensation Scheme Summary (Tier-2)")
        comp_table.add_column("Document", style="magenta")
        comp_table.add_column("Blocks", justify="right")
        comp_table.add_column("Compensation Types", justify="left")
        comp_table.add_column("Pages", justify="right")
        
        for comp_doc in compensation_docs:
            # Count unique compensation types
            comp_types = set()
            for block in comp_doc.blocks:
                if block.compensation_type:
                    comp_types.add(block.compensation_type)
            
            comp_table.add_row(
                comp_doc.short_name,
                str(len(comp_doc.blocks)),
                ", ".join(sorted(t.value for t in list(comp_types)[:3])) + ("..." if len(comp_types) > 3 else ""),
                str(comp_doc.total_pages)
            )
        
        console.print(comp_table)


@cli.command()
@click.option("--parsed-dir", "-p", default=str(PARSED_DIR), help="Directory with parsed JSON documents")
@click.option("--index-dir", "-i", default=str(INDEX_DIR), help="Output directory for indices")
@click.option("--model", "-m", default="sentence-transformers/all-MiniLM-L6-v2", help="Embedding model name")
def index(parsed_dir: str, index_dir: str, model: str):
    """Generate embeddings and build vector indices."""
    from src.models import LegalDocument
    from src.sop_parser import SOPDocument
    from src.evidence_parser import EvidenceManualDocument
    from src.compensation_parser import CompensationSchemeDocument
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
    evidence_docs = []
    compensation_docs = []
    
    for json_file in json_files:
        with open(json_file, "r", encoding="utf-8") as f:
            doc_dict = json.load(f)
            doc_type = doc_dict.get("doc_type", "")
            
            # Check document type and load accordingly
            if doc_type == "SOP":
                sop_docs.append(SOPDocument.from_dict(doc_dict))
                console.print(f"[green]Loaded SOP:[/green] {json_file.name}")
            elif doc_type == "EVIDENCE_MANUAL":
                evidence_docs.append(EvidenceManualDocument.from_dict(doc_dict))
                console.print(f"[cyan]Loaded Evidence Manual:[/cyan] {json_file.name}")
            elif doc_type == "COMPENSATION_SCHEME":
                compensation_docs.append(CompensationSchemeDocument.from_dict(doc_dict))
                console.print(f"[magenta]Loaded Compensation Scheme:[/magenta] {json_file.name}")
            else:
                documents.append(LegalDocument.from_dict(doc_dict))
                console.print(f"[blue]Loaded:[/blue] {json_file.name}")
    
    # Initialize embedder
    embedder = HierarchicalEmbedder(model_name=model)
    
    # Generate embeddings for all legal documents
    for doc in documents:
        embedder.embed_document(doc)
    
    # Generate embeddings for SOP documents (Tier-1)
    for sop in sop_docs:
        console.print(f"[green]Embedding SOP:[/green] {sop.short_name}")
        embedder.embed_sop_document(sop)
    
    # Generate embeddings for Evidence Manual documents (Tier-2)
    for evidence_doc in evidence_docs:
        console.print(f"[cyan]Embedding Evidence Manual:[/cyan] {evidence_doc.short_name}")
        embedder.embed_evidence_document(evidence_doc)
    
    # Generate embeddings for Compensation Scheme documents (Tier-2)
    for comp_doc in compensation_docs:
        console.print(f"[magenta]Embedding Compensation Scheme:[/magenta] {comp_doc.short_name}")
        embedder.embed_compensation_document(comp_doc)
    
    # Build vector store
    assert embedder.embedding_dim is not None, "Embedding dimension not initialized"
    store = MultiLevelVectorStore(embedding_dim=embedder.embedding_dim)
    
    for doc in documents:
        store.add_document(doc)
    
    # Add SOP documents to store (Tier-1)
    for sop in sop_docs:
        store.add_sop_document(sop)
    
    # Add Evidence Manual documents to store (Tier-2)
    for evidence_doc in evidence_docs:
        store.add_evidence_document(evidence_doc)
    
    # Add Compensation Scheme documents to store (Tier-2)
    for comp_doc in compensation_docs:
        store.add_compensation_document(comp_doc)
    
    # Build BM25 indices
    store.build_bm25_indices()
    
    # Save indices
    store.save(index_path)
    
    # Print stats
    stats = store.get_stats()
    table = Table(title="Index Statistics")
    table.add_column("Level", style="cyan")
    table.add_column("Count", justify="right")
    
    # Legal documents
    table.add_row("Documents", str(stats["documents"]))
    table.add_row("Chapters", str(stats["chapters"]))
    table.add_row("Sections", str(stats["sections"]))
    table.add_row("Subsections", str(stats["subsections"]))
    
    # Tier-1: SOP
    if stats.get("sop_blocks", 0) > 0:
        table.add_row("SOP Blocks (Tier-1)", str(stats["sop_blocks"]))
    
    # Tier-2: Evidence and Compensation
    if stats.get("evidence_blocks", 0) > 0:
        table.add_row("Evidence Blocks (Tier-2)", str(stats["evidence_blocks"]))
    if stats.get("compensation_blocks", 0) > 0:
        table.add_row("Compensation Blocks (Tier-2)", str(stats["compensation_blocks"]))
    
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
    
    # Show Evidence blocks if present (Tier-2 feature)
    if result["retrieval"].get("evidence_blocks"):
        console.print("\n[bold cyan]🧪 Evidence & Investigation Standards Found:[/bold cyan]")
        evidence_table = Table(show_header=True, header_style="bold cyan")
        evidence_table.add_column("Topic", style="cyan", width=25)
        evidence_table.add_column("Guidance", width=55)
        evidence_table.add_column("If Not Followed", style="red", width=15)
        
        for block in result["retrieval"]["evidence_blocks"][:5]:
            title = block["metadata"].get("title", "")[:25]
            failure_impact = block["metadata"].get("failure_impact", "").replace("_", " ")
            evidence_table.add_row(
                title,
                block["text"][:180] + "..." if len(block["text"]) > 180 else block["text"],
                failure_impact if failure_impact else "-"
            )
        
        console.print(evidence_table)
    
    # Show Compensation blocks if present (Tier-2 feature)
    if result["retrieval"].get("compensation_blocks"):
        console.print("\n[bold magenta]💰 Compensation & Rehabilitation Found:[/bold magenta]")
        comp_table = Table(show_header=True, header_style="bold magenta")
        comp_table.add_column("Topic", style="magenta", width=25)
        comp_table.add_column("Details", width=50)
        comp_table.add_column("Amount", width=12)
        comp_table.add_column("Conviction?", width=10)
        
        for block in result["retrieval"]["compensation_blocks"][:5]:
            title = block["metadata"].get("title", "")[:25]
            amount = block["metadata"].get("amount_range", "-")
            requires_conviction = block["metadata"].get("requires_conviction", False)
            conviction_text = "Required" if requires_conviction else "NOT Required"
            comp_table.add_row(
                title,
                block["text"][:160] + "..." if len(block["text"]) > 160 else block["text"],
                amount if amount else "-",
                conviction_text
            )
        
        console.print(comp_table)
    
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
    
    # Show Tier-2 intent info
    tier2_info = []
    if result.get("needs_evidence"):
        tier2_info.append("Evidence/Investigation")
    if result.get("needs_compensation"):
        tier2_info.append("Compensation/Relief")
    if tier2_info:
        console.print(f"[dim]Tier-2 Context: {', '.join(tier2_info)}[/dim]")
    
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
        sop_table = Table(title="SOP Documents (Tier-1 Procedural)")
        sop_table.add_column("Metric", style="green")
        sop_table.add_column("Value", justify="right")
        
        sop_table.add_row("📘 SOP Blocks", str(sop_count))
        
        console.print(sop_table)
    
    # Tier-2 statistics (Evidence and Compensation)
    evidence_count = stats.get("evidence_blocks", 0)
    compensation_count = stats.get("compensation_blocks", 0)
    
    if evidence_count > 0 or compensation_count > 0:
        tier2_table = Table(title="Tier-2 Documents (Evidence & Compensation)")
        tier2_table.add_column("Metric", style="cyan")
        tier2_table.add_column("Value", justify="right")
        
        if evidence_count > 0:
            tier2_table.add_row("🧪 Evidence Blocks", str(evidence_count))
        if compensation_count > 0:
            tier2_table.add_row("💰 Compensation Blocks", str(compensation_count))
        
        console.print(tier2_table)
    
    # Technical info
    tech_table = Table(title="Technical Info")
    tech_table.add_column("Setting", style="dim")
    tech_table.add_column("Value", justify="right")
    
    tech_table.add_row("Embedding Dimension", str(stats["embedding_dim"]))
    tech_table.add_row("Index Location", str(index_path))
    tech_table.add_row("SOP Support (Tier-1)", "✅ Enabled" if sop_count > 0 else "❌ Not indexed")
    tech_table.add_row("Evidence Support (Tier-2)", "✅ Enabled" if evidence_count > 0 else "❌ Not indexed")
    tech_table.add_row("Compensation Support (Tier-2)", "✅ Enabled" if compensation_count > 0 else "❌ Not indexed")
    
    console.print(tech_table)


if __name__ == "__main__":
    cli()
