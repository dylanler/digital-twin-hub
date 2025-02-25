# Smart Influencer Hub - Digital Identity Studio Flow Diagrams

This document outlines the various flows and components of the Smart Influencer Hub application using Mermaid diagrams.

## 1. High-Level Application Flow
This diagram shows the main components and user interaction flow of the application.

```mermaid
graph TD
    A[Start] --> B[Gradio Web Interface]
    B --> C[Step 1: Create Digital Identity]
    B --> D[Step 2: Select Identity]
    B --> E[Step 3: Generate Content]
    
    C --> C1[Upload Photos ZIP]
    C --> C2[Set Trigger Word]
    C1 --> C3[Train LoRA Model]
    C2 --> C3
    
    D --> D1[Select Character LoRA]
    D --> D2[Select Environment LoRA]
    D --> D3[Select Object LoRA]
    
    E --> E1[Input Script/Description]
    E --> E2[Configure Parameters]
    E --> E3[Generate Video]
    
    E3 --> F[Final Video Output]
```

## 2. LoRA Training Flow
This sequence diagram illustrates the process of training a new LoRA model from user-provided images.

```mermaid
sequenceDiagram
    participant User
    participant UI as Gradio Interface
    participant Trainer as LoRA Trainer
    participant Storage as File Storage
    
    User->>UI: Upload ZIP file
    User->>UI: Enter trigger word
    User->>UI: Click "Create Digital Identity"
    UI->>Trainer: Initialize LoRA training
    Trainer->>Trainer: Process images
    Trainer->>Trainer: Train LoRA model
    Trainer->>Storage: Save LoRA config
    Storage->>UI: Return config filename
    UI->>User: Display completion status
```

## 3. Video Generation Pipeline
This diagram shows how the video generation process flows from script input to final output.

```mermaid
graph LR
    A[Script Input] --> B[Scene Analysis]
    B --> C[Generate Metadata]
    C --> D[Generate Scenes]
    
    D --> E[First Frame Generation]
    D --> F[Video Generation]
    D --> G[Sound Effects]
    
    E --> H[Multi-LoRA Processing]
    H --> F
    
    F --> I[Video Stitching]
    G --> I
    
    I --> J[Final Video]
```

## 4. Scene Generation Process
This flowchart details how scenes are generated from the input script.

```mermaid
flowchart TD
    A[Script] --> B[LLM Analysis]
    B --> C{Generate Components}
    
    C --> D[Physical Environments]
    C --> E[Scene Metadata]
    C --> F[Movement Descriptions]
    C --> G[Camera Instructions]
    
    D --> H[Scene Assembly]
    E --> H
    F --> H
    G --> H
    
    H --> I[Video Generation Engine]
    I --> J[Luma]
    I --> K[LTX]
    I --> L[FAL]
```

## 5. Component Data Flow
This diagram illustrates how data flows between different components of the system.

```mermaid
graph TD
    subgraph UI[Gradio Interface]
        A[Input Forms]
        B[Status Display]
        C[Video Preview]
    end
    
    subgraph Processing[Backend Processing]
        D[LoRA Training]
        E[Video Generation]
        F[Scene Generation]
        G[Multi-LoRA Inference]
    end
    
    subgraph Storage[File Storage]
        H[LoRA Configs]
        I[Generated Videos]
        J[Temporary Files]
    end
    
    A --> D
    D --> H
    H --> G
    G --> E
    F --> E
    E --> I
    I --> C
    E --> B
```

## Technical Components Summary

The application integrates several key technologies:

1. **Frontend**:
   - Gradio web interface for user interaction
   - Real-time status updates
   - Video preview capabilities

2. **AI Models**:
   - LoRA for fine-tuning stable diffusion models
   - Multiple video generation engines (Luma, LTX, FAL)
   - LLM integration (Gemini, Claude) for content analysis

3. **Processing**:
   - Multi-LoRA inference for enhanced image generation
   - Scene generation and analysis
   - Video stitching and post-processing

4. **Storage**:
   - LoRA configuration management
   - Temporary file handling
   - Generated video storage

The system is designed with modularity in mind, allowing for easy updates and component replacements while maintaining the core workflow. 