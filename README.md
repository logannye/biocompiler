# biocompiler

### A compiler for programming the immune system.

**Our long-term vision is a system that humans or AI agents can use to specify arbitrary therapeutic programs for a given patient's immune system, then deterministically and correctly compile those programs into biological payloads for in vivo administration.**

The ambition is to make a patient's therapeutic strategy programmable: describe what their immune cells should recognize, remember, and do over time, then translate that strategy into exact RNA instructions intended to implement it inside the body. Researchers, clinicians, and agents could work with the same explicit program, with a traceable path from each requirement to the resulting payload.

Here, *arbitrary* describes the breadth of programs we aim to let people express and compose. Successful compilation would still require a realizable implementation under the system's models and constraints; a program without one should receive an explanation of what is missing. The goal is a general programming system for human immune-cell therapies.

**Today, biocompiler is experimental research software building toward that future.** Python is the current authoring language. Supported compilation profiles produce exact RNA payload specifications with records of their components, assumptions, and checks. Human immune cells engineered inside the body—*in vivo*—are its product focus.

[What works today](#what-works-today) · [The long-term vision](#the-next-1020-years) · [Explore the project](#explore-the-project)

## Medicine that responds to context

Imagine an immune-cell therapy programmed to dynamically respond to the patient's body: recognize a combination of disease signals, respond only when the required conditions are present, remember an earlier encounter, and change its response as a treatment progresses. Its specification would also describe when activity must stop and what outcomes must be avoided.

That is the kind of therapeutic program we want researchers to be able to express and patients to be able to receive. This example illustrates the direction of the project.

Turning such detailed therapeutic intent into a corresponding RNA medicine involves many linked decisions. Which molecular components could implement it? Can they work together under the stated assumptions? Does stopping production also stop an existing product's activity? Does the final sequence still correspond to the original design?

**biocompiler brings those questions into one inspectable engineering workflow.**

## What it is useful for

- **Making therapeutic ideas precise.** Programmatically specify recognition, timing, memory, actions, and constraints so that collaborators can inspect the same design.
- **Finding design problems earlier.** Expose missing implementations, incompatible component contracts, and unsupported requirements before treating a design as complete.
- **Comparing implementation choices.** Evaluate supplied alternatives against explicit requirements and track why a candidate was selected or rejected.
- **Producing reproducible RNA designs.** Emit exact nucleotide sequences with the information needed to trace them back to their source requirements and check them again.

The immediate users for biocompiler include researchers and engineers developing programmable immune-cell therapies. The intended benefit is a more disciplined path from an idea to a candidate ready for experimental investigation compared to the bespoke processes of today.

## Why a compiler matters

A software compiler translates a program into machine code instructions while preserving its meaning, lowering the information through a succession of intermediate representations until it is correctly encoded in 0's and 1's. Biocompiler does this same thing, but applied to therapeutic design - it just encodes the programmatic logic into biomolecules instead of silicon:

```text
Therapeutic intent + supplied component models and sequence templates
                                ↓
                Explicit implementation and composition
                                ↓
                  Exact RNA design + independent checks
```

The distinguishing aim is **a traceable connection between intended behavior, the proposed implementation, and every emitted molecular payload**. Generative models could supply new candidate components; a compiler provides a framework for checking how supported components are assembled into a specified system.

For supported profiles, biocompiler retains requirements through translation, checks component relationships, and reconstructs results against the original inputs. Unsupported meaning remains visible. A complete compilation claim requires the relevant obligations to pass within the declared model and checking bounds.

In the mature system, **deterministic** would mean that the same complete specification, patient-context inputs, versioned component library, and compiler version and configuration produce the same payload or the same explained rejection. **Correct** would mean that the translation preserves the program's specified meaning through component composition and exact RNA construction under explicit assumptions. Human and agent authors would benefit from the same checks.

Delivery, biological function, safety, and therapeutic benefit require their own evidence. The software is designed to keep those claims separate and their dependencies explicit.

## What works today

The repository contains working research software for:

| Capability | What it means |
| --- | --- |
| Python authoring | Structured descriptions of therapeutic intent, including recognition, timing, state, effects, and coordinated cell roles. |
| Bounded compilation | Supported executable profiles connect specified behavior to supplied component implementations and exact RNA designs. |
| Composition and control checks | Explicit checks for supported state, timing, control, helper, and deployment relationships under declared contracts. |
| Independent verification and export | Recheck source-to-implementation correspondence and sequence construction; export RNA sequences with a detailed manifest. |
| Inspection and reproducibility | Preserve inputs, alternatives, diagnostics, and build records; explore an artificial example in a local browser workspace. |

Importantly, a feature appearing in the Python vocabulary does not mean every combination can already compile to RNA. See the [architecture profile](docs/payload-architecture-v0.1.md), [policy language](docs/policy-language-v0.1.md), and [semantic mRNA development plan](docs/semantic-mrna-development-plan.md) for precise boundaries and status.

Bundled design examples use artificial, nonfunctional molecular fixtures. They exercise the software, not a validated therapy. biocompiler is experimental research software and does not currently establish readiness for human use.

## Why this is worth building

Three developments make the direction concrete:

1. **Engineered immune cells are already medicines.** FDA-approved CAR T-cell therapies such as [Kymriah](https://www.fda.gov/vaccines-blood-biologics/cellular-gene-therapy-products/kymriah) demonstrate that genetically modified immune cells can become therapeutic products.
2. **Engineering cells inside the body is an active research frontier.** A [2025 study in *Science*](https://pubmed.ncbi.nlm.nih.gov/40536974/) reported targeted mRNA delivery to T cells, with tumor control in humanized mice and B-cell depletion in monkeys. Those are preclinical results, distinct from proof of human therapeutic benefit.
3. **AI is expanding the set of molecular designs researchers can explore.** [RFdiffusion](https://www.nature.com/articles/s41586-023-06415-8) demonstrated generative protein design with experimental characterization of designed structures and functions.

These advances motivate our thesis: **as the ability for humans and agents to generate biological components improves, programmatically specifying and checking the systems assembled from them could become increasingly valuable.**

## The next 10–20 years

We are starting with immune cell engineering, but the long-term vision we are building towards is **a general-purpose compiler for patient-specific therapeutic programs**. A human or agent would specify a strategy for a particular patient's immune system: the disease context to recognize, the cells to engineer, the sequence of responses, the state to retain, and the conditions for changing or stopping activity. biocompiler would translate the complete program into an exact RNA payload, potentially comprising several coordinated RNA molecules, intended for in vivo administration.

The therapeutic program would become a shared interface between clinical reasoning, AI-assisted design, molecular engineering, and experimental science. A clinician could state a treatment objective, a researcher could refine its cellular behavior, and an agent could explore candidate implementations. Each proposed revision would remain explicit, versioned, and subject to the same compilation and verification requirements, with human oversight of therapeutic decisions.

If the necessary delivery technologies, biological models, and experimental evidence mature, that environment could support:

- **Therapies expressed as complete programs:** compose sensing, memory, staged regimens, coordinated cell roles, and stopping conditions into an integrated strategy.
- **The patient as the unit of design:** adapt recognition, response, timing, and constraints to an individual's disease context while retaining product-specific validation requirements.
- **A common interface for humans and agents:** let either author propose and revise a therapeutic program, inspect why compilation succeeds or fails, and compare reproducible payload designs.
- **Reusable biological knowledge:** component libraries that record where a behavior has been demonstrated, what it depends on, and where it fails.
- **A tighter scientific learning loop:** connect design, automated experiments, measurement, and model revision so that each experiment can improve subsequent designs under human oversight.

The most ambitious outcome is an integrated system for designing, compiling, and experimentally refining programmable medicines. Agents could help propose programs and informative experiments; automated laboratories could test candidates; results could refine the component models used in subsequent compilations. Knowledge gained while developing one therapy could make the next program easier to engineer, wherever that knowledge demonstrably applies.

Over 10–20 years, our aspiration is for the path from a patient-specific therapeutic strategy to a precisely specified biological payload to become a repeatable engineering process. Broad program compilation, natural-language authoring, clinical workflows, and laboratory integration belong to this future vision; they are not delivered capabilities today.

## The opportunity we see

The thesis is a shared compilation and verification layer through which many humans, agents, and therapeutic programs could work. Each patient's strategy may differ, while the language, compiler, component knowledge, and verification infrastructure can be reused. Better delivery methods and better molecular components could expand what that infrastructure can support.

We see three possibilities worth testing over the coming decades:

- As designs grow more complex, the cost of integrating and checking components may become as consequential as generating them.
- Experimentally grounded component libraries and records connecting predictions to outcomes could become durable assets.
- Reusing a trustworthy design-and-verification workflow across programs could reduce duplicated engineering and make scientific iteration more productive.

## Researcher alpha workflow

The [researcher-alpha roadmap](docs/researcher-alpha-roadmap.md) tracks the current
lab-free delivery work. Its [quickstart](docs/researcher-alpha-quickstart.md)
introduces caller-owned projects, complete original-input preservation, separate
Core compilation and Verify export, and fresh verification of the exact
FASTA/manifest pair. The first two examples are explicitly artificial software
references. Hosted installation and release acceptance, qualification of a useful
real research project, and independent researcher review remain separate gates.

## Explore the project

Start with the [example guide](examples/README.md) or the [guided workspace](docs/studio-v0.1.md). From a source checkout with Python 3.11 or newer, launch the local browser example without installing:

```sh
PYTHONPATH=src python3 -m biocompiler studio
```

The workspace demonstrates the earlier structural candidate workflow using artificial parts. It is an introduction to inspecting designs; the broader compiler profiles are documented separately.

| Explore | Start here |
| --- | --- |
| Design and direction | [Product vision and integration roadmap](docs/product-vision-and-integration-roadmap.md) · [Architecture](docs/architecture.md) · [Roadmap](docs/roadmap.md) |
| Therapeutic programs | [Python policy language](docs/policy-language-v0.1.md) · [Executable RNA architecture](docs/payload-architecture-v0.1.md) |
| Correctness and evidence | [Verification independence](docs/verification-independence-v0.1.md) · [Human-use admission boundaries](docs/human-admission-v0.1.md) |
| Contributing | [Source](src/biocompiler/) · [Tests](tests/README.md) · [Engineering guidelines](AGENTS.md) |

We welcome conversations with researchers, compiler engineers, experimental collaborators, and early-stage partners who want to help build this future. [Open an issue](https://github.com/logannye/biocompiler/issues) to discuss the project or a potential collaboration.
