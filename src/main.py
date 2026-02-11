import os
import click
import json
from typing import Optional
from .providers.github_provider import GitHubProvider
from .domain import ReviewResult
from .safety.env_loader import load_env_file

# Load local environment variables before Click resolves envvar-based options.
load_env_file(".env")

@click.group()
def cli():
    """AI Code Review CLI"""
    pass

@cli.command()
@click.option('--provider', type=click.Choice(['github', 'gitlab']), default='github', help='Git forge provider')
@click.option('--token', envvar='GITHUB_TOKEN', help='API Token')
@click.option('--repo', envvar='GITHUB_REPOSITORY', help='Repository slug (owner/repo)')
@click.option('--pr', type=int, envvar='PR_NUMBER', help='Pull Request Number')
@click.option('--openai-key', envvar='OPENAI_API_KEY', help='OpenAI API Key')
@click.option('--dry-run', is_flag=True, help='Do not post comments')
def review(provider: str, token: str, repo: str, pr: int, openai_key: str, dry_run: bool):
    """Run code review on a Pull Request."""
    click.echo(f"Starting review for {repo} PR #{pr} using {provider}...")
    
    if provider == 'github':
        if not token:
            raise click.UsageError("GitHub token is required. Set GITHUB_TOKEN or pass --token.")
        git_provider = GitHubProvider(token=token, repo_slug=repo, pr_number=pr)
    else:
        raise NotImplementedError("GitLab provider not yet implemented.")

    # 1. Fetch Metadata
    meta = git_provider.fetch_pr_metadata()
    click.echo(f"Title: {meta['title']}")
    
    # 2. Get Changed Files
    files = git_provider.get_changed_files()
    click.echo(f"Found {len(files)} changed files.")
    
    # 3. Context Builder
    from .context_builder.builder import ContextBuilder
    builder = ContextBuilder(workspace_root=".")
    docs_paths = builder.load_project_docs()
    
    # 4. Filters
    from .filters.filter import FileFilter
    filtr = FileFilter()
    filter_result = filtr.filter_files(files)
    click.echo(f"Filter: {len(filter_result.files_to_review)} files to review (Risk Score: {filter_result.risk_score})")
    
    # 5. Retrieval
    from .retrieval.engine import DocRetriever
    retriever = DocRetriever()
    if docs_paths:
        retriever.index_documents(docs_paths)
        click.echo(f"Indexed {len(docs_paths)} docs for evidence retrieval.")
    else:
        click.echo("No project docs found for retrieval.")
    
    # 6. Review Logic
    from .review.llm import LLMClient
    from .review.analyzer import ReviewAnalyzer
    from .policy.manager import PolicyManager
    
    llm = LLMClient(api_key=openai_key)
    analyzer = ReviewAnalyzer(llm)
    
    # Triage
    click.echo("Running Triage...")
    triage_plan = analyzer.triage(filter_result, meta)
    click.echo(f"Triage Plan: {json.dumps(triage_plan, indent=2)}")
    
    files_to_review_paths = triage_plan.get("files_to_review", [])
    
    # Focused Review
    all_issues = []
    click.echo("Running Focused Review...")
    for file in filter_result.files_to_review:
        if file.path in files_to_review_paths:
            click.echo(f"Reviewing {file.path}...")
            # Retrieve specific docs (mock query)
            evidence = retriever.retrieve_relevant_docs(f"standards for {file.path}")
            
            file_issues = analyzer.review_file(file, evidence)
            all_issues.extend(file_issues)
            
    # 7. Policy
    policy = PolicyManager()
    final_issues = policy.apply_policy(all_issues)
    
    # Decision
    # We DO NOT fail the job based on issues anymore (as per MVP critical feedback).
    # We only report status.
    decision = "PASS"
    for issue in final_issues:
        if issue.severity == "BLOCKER":
            decision = "WARN" # Was FAILL
            break
        if issue.severity == "IMPORTANT":
            decision = "WARN"

    # 8. Renderer
    from .renderer.renderer import Renderer
    renderer = Renderer()
    
    summary_text = triage_plan.get("summary", "Review completed.") # Triage might not return summary, maybe generate it?
    # Actually let's just use a simple summary for now
    summary_text = f"Reviewed {len(files_to_review_paths)} files. Found {len(final_issues)} issues."

    result = ReviewResult(
        summary=summary_text,
        issues=final_issues,
        stats={"risk_score": filter_result.risk_score, "files_analyzed": len(files_to_review_paths)},
        decision=decision
    )
    
    summary_md = renderer.to_github_summary(result, filter_result.risk_score)
    
    # 9. Post Results
    # Save result.json
    with open("result.json", "w", encoding="utf-8") as f:
        f.write(renderer.to_json(result))
    
    if not dry_run:
        git_provider.post_summary_comment(summary_md)
        # Enforce max_inline limit for inline comments specifically
        # We use strict slicing on the final sorted list
        inline_issues = result.issues[:policy.max_inline]
        git_provider.post_inline_comments(inline_issues)
        click.echo("Posted comments.")
    else:
        click.echo("Dry run: Skipping comment posting.")
        click.echo(summary_md)
        click.echo(renderer.to_json(result))

if __name__ == '__main__':
    cli()
