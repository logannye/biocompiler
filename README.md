# biocompiler

### From therapeutic intent to traceable RNA designs.

**biocompiler is an experimental compiler for programmable medicine.** It is being built to turn a precise description of what engineered human immune cells should do into the RNA instructions intended to implement that behavior.

The input is a therapeutic program, written in Python. The output, for supported compilation profiles, is an exact RNA payload specification together with a record of its components, assumptions, and checks. Its product focus is **human immune cells engineered inside the body**—an approach called *in vivo* engineering.

Our ambition is to make increasingly sophisticated cellular therapies something researchers can **describe, compose, inspect, and improve systematically**.

[What works today](#what-works-today) · [The long-term vision](#the-next-1020-years) · [Explore the project](#explore-the-project)

## Medicine that responds to context

Imagine an immune-cell therapy designed to recognize a combination of disease signals, respond only when the required conditions are present, remember an earlier encounter, and change its response as a treatment progresses. Its specification would also describe when activity must stop and what outcomes must be avoided.

That is the kind of therapeutic program we want researchers to be able to express. This example illustrates the direction of the project; it is not a treatment produced or validated by biocompiler.

Turning such intent into RNA involves many linked decisions. Which molecular components could implement it? Can they work together under the stated assumptions? Does stopping production also stop an existing product's activity? Does the final sequence still correspond to the original design?

**biocompiler brings those questions into one inspectable engineering workflow.**

## What it is useful for

- **Making therapeutic ideas precise.** Specify recognition, timing, memory, actions, and constraints so that collaborators can inspect the same design.
- **Finding design problems earlier.** Expose missing implementations, incompatible component contracts, and unsupported requirements before treating a design as complete.
- **Comparing implementation choices.** Evaluate supplied alternatives against explicit requirements and retain why a candidate was selected or rejected.
- **Producing reproducible RNA designs.** Emit exact nucleotide sequences with the information needed to trace them back to their source requirements and check them again.

The immediate audience is researchers and engineers developing programmable immune-cell therapies. The intended benefit is a more disciplined path from an idea to a candidate ready for experimental investigation.

## Why a compiler matters

A software compiler translates a program into instructions while preserving its meaning. biocompiler applies that engineering principle to therapeutic design:

```text
Therapeutic intent + supplied component models and sequence templates
                                ↓
                Explicit implementation and composition
                                ↓
                  Exact RNA design + independent checks
```

The distinguishing aim is **a traceable connection between intended behavior, the proposed implementation, and every emitted RNA molecule**. Generative models could supply new candidate components; a compiler provides a framework for checking how supported components are assembled into a specified system.

For supported profiles, biocompiler retains requirements through translation, checks component relationships, and reconstructs results against the original inputs. Unsupported meaning remains visible. A complete compilation claim requires the relevant obligations to pass within the declared model and checking bounds.

This distinction is essential: **correct translation under a model does not establish that the model holds in a living cell.** Delivery, biological function, safety, and therapeutic benefit require their own evidence. The software is designed to keep those claims separate and their dependencies explicit.

## What works today

The repository contains working research software for:

| Capability | What it means |
| --- | --- |
| Python authoring | Structured descriptions of therapeutic intent, including recognition, timing, state, effects, and coordinated cell roles. |
| Bounded compilation | Supported executable profiles connect specified behavior to supplied component implementations and exact RNA designs. |
| Composition and control checks | Explicit checks for supported state, timing, control, helper, and deployment relationships under declared contracts. |
| Independent verification and export | Recheck source-to-implementation correspondence and sequence construction; export RNA sequences with a detailed manifest. |
| Inspection and reproducibility | Preserve inputs, alternatives, diagnostics, and build records; explore an artificial example in a local browser workspace. |

Authoring is broader than executable compilation. The newer expressive policy pipeline has its own staged implementation and acceptance work; a feature appearing in the Python vocabulary does not mean every combination can already compile to RNA. See the [architecture profile](docs/payload-architecture-v0.1.md), [policy language](docs/policy-language-v0.1.md), and [semantic mRNA development plan](docs/semantic-mrna-development-plan.md) for precise boundaries and status.

Bundled design examples use artificial, nonfunctional molecular fixtures. They exercise the software, not a validated therapy. biocompiler is experimental research software and does not currently establish readiness for human use.

## Why this is worth building now

Three developments make the direction concrete:

1. **Engineered immune cells are already medicines.** FDA-approved CAR T-cell therapies such as [Kymriah](https://www.fda.gov/vaccines-blood-biologics/cellular-gene-therapy-products/kymriah) demonstrate that genetically modified immune cells can become therapeutic products.
2. **Engineering cells inside the body is an active research frontier.** A [2025 study in *Science*](https://pubmed.ncbi.nlm.nih.gov/40536974/) reported targeted mRNA delivery to T cells, with tumor control in humanized mice and B-cell depletion in monkeys. Those are preclinical results, distinct from proof of human therapeutic benefit.
3. **AI is expanding the set of molecular designs researchers can explore.** [RFdiffusion](https://www.nature.com/articles/s41586-023-06415-8) demonstrated generative protein design with experimental characterization of designed structures and functions.

These are advances by other research teams, not validations of biocompiler. They motivate our thesis: **as the ability to generate biological components improves, specifying and checking the systems assembled from them could become increasingly valuable.**

## The next 10–20 years

Our long-term vision is a development environment for programmable human immunity: researchers describe a therapeutic strategy, explore possible implementations, inspect what is known and unknown, and carry a reproducible design into experiments.

If the necessary delivery technologies, biological models, and experimental evidence mature, that environment could support:

- **Therapies with richer behavior:** combinations of sensing, memory, staged responses, and explicitly designed stopping conditions.
- **More individualized designs:** adapting a program to a patient's disease context while retaining traceability and product-specific validation requirements.
- **Reusable biological knowledge:** component libraries that record where a behavior has been demonstrated, what it depends on, and where it fails.
- **A tighter scientific learning loop:** connect design, automated experiments, measurement, and model revision so that each experiment can improve subsequent designs under human oversight.

The most ambitious outcome is a system in which therapeutic engineering becomes more cumulative: a successful experiment improves both one candidate and the knowledge available to future programs. Natural-language authoring and laboratory integration belong to this future vision; they are not delivered capabilities today.

## The opportunity we see

For an early-stage investor, the thesis is infrastructure that could become useful across many therapeutic programs. Better delivery methods and better molecular components could expand what such infrastructure can support.

We see three possibilities worth testing over the coming decades:

- As designs grow more complex, the cost of integrating and checking components may become as consequential as generating them.
- Experimentally grounded component libraries and records connecting predictions to outcomes could become durable assets.
- Reusing a trustworthy design-and-verification workflow across programs could reduce duplicated engineering and make scientific iteration more productive.

That is the asymmetric opportunity we are pursuing. Its value must be earned through broader end-to-end capabilities, independent experimental collaborations, and measurable improvements in researchers' workflows. These are hypotheses and milestones, not claims of established adoption or clinical performance.

## Explore the project

Start with the [example guide](examples/README.md) or the [guided workspace](docs/studio-v0.1.md). From a source checkout with Python 3.11 or newer, launch the local browser example without installing:

```sh
PYTHONPATH=src python3 -m biocompiler studio
```

The workspace demonstrates the earlier structural candidate workflow using artificial parts. It is an introduction to inspecting designs; the broader compiler profiles are documented separately.

| Explore | Start here |
| --- | --- |
| Design and direction | [Architecture](docs/architecture.md) · [Roadmap](docs/roadmap.md) |
| Therapeutic programs | [Python policy language](docs/policy-language-v0.1.md) · [Executable RNA architecture](docs/payload-architecture-v0.1.md) |
| Correctness and evidence | [Verification independence](docs/verification-independence-v0.1.md) · [Human-use admission boundaries](docs/human-admission-v0.1.md) |
| Contributing | [Source](src/biocompiler/) · [Tests](tests/README.md) · [Engineering guidelines](AGENTS.md) |

We welcome conversations with researchers, compiler engineers, experimental collaborators, and early-stage partners who want to help build this future. [Open an issue](https://github.com/logannye/biocompiler/issues) to discuss the project or a potential collaboration.
