param(
    [ValidateSet("sync", "smoke", "action-train", "prose-train", "prose-exact-train", "buddy-distill", "buddy-fetch", "full-eval")]
    [string]$Mode = "sync",
    [string]$RemoteHost = "snacksack",
    [string]$RemoteRoot = "~/projects/PixieologyRemote",
    [string]$RemoteDataRoot = "~/pixie-data",
    [string]$RemoteHubCache = "",
    [string]$LocalDataRoot = "",
    [string]$TrainQloraPath = "",
    [string]$SoulPath = "",
    [string]$ComparisonPath = "",
    [string]$OutputTag = "",
    [string]$BuddyDate = "",
    [string]$AdapterPath = ""
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSCommandPath
$Config = Get-Content -Raw (Join-Path $RepoRoot "pixieology.config.json") | ConvertFrom-Json

function Resolve-ConfigPath {
    param([string]$Value)
    if ([System.IO.Path]::IsPathRooted($Value)) { return $Value }
    return [System.IO.Path]::GetFullPath((Join-Path $RepoRoot $Value))
}

if (-not $LocalDataRoot) {
    $LocalDataRoot = Resolve-ConfigPath $Config.paths.data_root
}
if (-not $TrainQloraPath) {
    $TrainQloraPath = Resolve-ConfigPath $Config.paths.tesseract_train_script
}
if (-not $SoulPath) {
    $SoulPath = Resolve-ConfigPath $Config.paths.soul_path
}
if (-not $ComparisonPath) {
    $ComparisonPath = Resolve-ConfigPath $Config.paths.storyworld_comparison_path
}
if (-not $RemoteHubCache) {
    $RemoteHubCache = "$RemoteDataRoot/hf_home/hub"
}

$SyncFiles = @(
    @{ Local = (Join-Path $RepoRoot "pixieology.config.json"); Remote = "$RemoteRoot/pixieology.config.json" },
    @{ Local = (Join-Path $RepoRoot "pixie_env.py"); Remote = "$RemoteRoot/pixie_env.py" },
    @{ Local = (Join-Path $RepoRoot "build_faebench_env.py"); Remote = "$RemoteRoot/build_faebench_env.py" },
    @{ Local = (Join-Path $RepoRoot "build_pixie_storyworld_sft_env.py"); Remote = "$RemoteRoot/build_pixie_storyworld_sft_env.py" },
    @{ Local = (Join-Path $RepoRoot "build_reflective_buddy_experiment.py"); Remote = "$RemoteRoot/build_reflective_buddy_experiment.py" },
    @{ Local = (Join-Path $RepoRoot "build_pixue_soul_env.py"); Remote = "$RemoteRoot/build_pixue_soul_env.py" },
    @{ Local = (Join-Path $RepoRoot "run_faebench_compare.py"); Remote = "$RemoteRoot/run_faebench_compare.py" },
    @{ Local = (Join-Path $RepoRoot "run_pixie_storyworld_sft.py"); Remote = "$RemoteRoot/run_pixie_storyworld_sft.py" },
    @{ Local = (Join-Path $RepoRoot "run_reflective_buddy_cron.sh"); Remote = "$RemoteRoot/run_reflective_buddy_cron.sh" },
    @{ Local = (Join-Path $RepoRoot "generate_reflective_buddy_distill.py"); Remote = "$RemoteRoot/generate_reflective_buddy_distill.py" },
    @{ Local = (Join-Path $RepoRoot "fae_constitution_seed.jsonl"); Remote = "$RemoteRoot/inputs/fae_constitution_seed.jsonl" },
    @{ Local = $SoulPath; Remote = "$RemoteRoot/inputs/soul.md" },
    @{ Local = $ComparisonPath; Remote = "$RemoteRoot/inputs/route_ablation_comparison.json" },
    @{ Local = $TrainQloraPath; Remote = "$RemoteRoot/external/train_qlora.py" }
)

function Invoke-Remote {
    param([string]$Command)
    & ssh $RemoteHost $Command
    if ($LASTEXITCODE -ne 0) {
        throw "Remote command failed: $Command"
    }
}

function Copy-RemoteFile {
    param(
        [string]$LocalPath,
        [string]$RemotePath
    )
    if (-not (Test-Path $LocalPath)) {
        throw "Missing local file: $LocalPath"
    }
    & scp $LocalPath "${RemoteHost}:$RemotePath"
    if ($LASTEXITCODE -ne 0) {
        throw "scp failed for $LocalPath -> $RemotePath"
    }
}

function Copy-FromRemoteFile {
    param(
        [string]$RemotePath,
        [string]$LocalPath
    )
    $localDir = Split-Path -Parent $LocalPath
    if ($localDir) {
        New-Item -ItemType Directory -Force -Path $localDir | Out-Null
    }
    if (Test-Path $LocalPath) {
        Remove-Item -Force $LocalPath
    }
    & scp "${RemoteHost}:$RemotePath" $LocalPath
    if ($LASTEXITCODE -ne 0) {
        throw "scp failed for $RemotePath -> $LocalPath"
    }
}

function Copy-FromRemoteFileIfExists {
    param(
        [string]$RemotePath,
        [string]$LocalPath
    )
    & ssh $RemoteHost "test -f $RemotePath"
    if ($LASTEXITCODE -ne 0) {
        return $false
    }
    Copy-FromRemoteFile -RemotePath $RemotePath -LocalPath $LocalPath
    return $true
}

function Ensure-RemoteDirs {
    $dirs = @(
        $RemoteRoot,
        "$RemoteRoot/inputs",
        "$RemoteRoot/external",
        "$RemoteDataRoot",
        "$RemoteDataRoot/normalized_trajectories",
        "$RemoteDataRoot/pixie_research",
        "$RemoteDataRoot/models_cache",
        "$RemoteDataRoot/hf_home",
        $RemoteHubCache
    )
    Invoke-Remote ("mkdir -p " + ($dirs -join " "))
}

function Sync-Workspace {
    Ensure-RemoteDirs
    foreach ($entry in $SyncFiles) {
        Copy-RemoteFile -LocalPath $entry.Local -RemotePath $entry.Remote
    }
}

function Remote-PixieEnvPrefix {
    return "HF_HOME=$RemoteDataRoot/hf_home HUGGINGFACE_HUB_CACHE=$RemoteHubCache PIXIE_DATA_ROOT=$RemoteDataRoot PIXIE_MODEL_CACHE_DIR=$RemoteHubCache"
}

function Default-Tag {
    param([string]$Prefix)
    if ($OutputTag) {
        return $OutputTag
    }
    return "$Prefix-$(Get-Date -Format yyyy-MM-dd_HHmmss)"
}

function Resolve-BuddyDate {
    if ($BuddyDate) {
        return $BuddyDate
    }
    $latest = & ssh $RemoteHost "python3 - <<'PY'
from pathlib import Path
root = Path('$RemoteDataRoot'.replace('~', str(Path.home()))) / 'pixie_research'
dates = []
patterns = [
    ('reflective_buddy_teacher_manifest_*.json', 'reflective_buddy_teacher_manifest_'),
    ('reflective_buddy_teacher_memory_*.jsonl', 'reflective_buddy_teacher_memory_'),
    ('reflective_buddy_teacher_*.jsonl', 'reflective_buddy_teacher_'),
    ('reflective_buddy_teacher_log_*.jsonl', 'reflective_buddy_teacher_log_'),
]
for pattern, prefix in patterns:
    for path in root.glob(pattern):
        suffix = path.stem.replace(prefix, '')
        if suffix:
            dates.append(suffix)
if dates:
    print(sorted(dates)[-1])
PY"
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to resolve latest buddy date on $RemoteHost"
    }
    if ($null -eq $latest) {
        return ""
    }
    $latest = "$latest".Trim()
    return $latest
}

switch ($Mode) {
    "sync" {
        Sync-Workspace
    }
    "smoke" {
        Sync-Workspace
        $envPrefix = Remote-PixieEnvPrefix
        Invoke-Remote "$envPrefix python3 $RemoteRoot/build_faebench_env.py --output $RemoteDataRoot/normalized_trajectories/faebench.jsonl --manifest $RemoteDataRoot/pixie_research/faebench_manifest.json"
        Invoke-Remote "$envPrefix python3 $RemoteRoot/run_faebench_compare.py --help >/dev/null"
    }
    "action-train" {
        Sync-Workspace
        $envPrefix = Remote-PixieEnvPrefix
        $tag = Default-Tag -Prefix "pixie_snacksack_action"
        $cmd = @(
            $envPrefix,
            "python3 $RemoteRoot/run_pixie_storyworld_sft.py",
            "--models 1.7B",
            "--skip-mixed-pass",
            "--skip-prose-pass",
            "--skip-bridge",
            "--pixie-root $RemoteRoot",
            "--merge-env $RemoteRoot/build_pixie_storyworld_sft_env.py",
            "--tesseract-train $RemoteRoot/external/train_qlora.py",
            "--soul-path $RemoteRoot/inputs/soul.md",
            "--constitution-path $RemoteRoot/inputs/fae_constitution_seed.jsonl",
            "--comparison-path $RemoteRoot/inputs/route_ablation_comparison.json",
            "--data-root $RemoteDataRoot",
            "--action-save-steps 1000",
            "--save-total-limit 1",
            "--output-root $RemoteDataRoot/pixie_research/$tag"
        ) -join " "
        Invoke-Remote $cmd
    }
    "prose-train" {
        Sync-Workspace
        $envPrefix = Remote-PixieEnvPrefix
        $tag = Default-Tag -Prefix "pixie_snacksack_prose"
        $cmd = @(
            $envPrefix,
            "python3 $RemoteRoot/run_pixie_storyworld_sft.py",
            "--models 1.7B",
            "--skip-mixed-pass",
            "--skip-action-pass",
            "--skip-bridge",
            "--pixie-root $RemoteRoot",
            "--merge-env $RemoteRoot/build_pixie_storyworld_sft_env.py",
            "--tesseract-train $RemoteRoot/external/train_qlora.py",
            "--soul-path $RemoteRoot/inputs/soul.md",
            "--constitution-path $RemoteRoot/inputs/fae_constitution_seed.jsonl",
            "--comparison-path $RemoteRoot/inputs/route_ablation_comparison.json",
            "--data-root $RemoteDataRoot",
            "--prose-save-steps 1000",
            "--save-total-limit 1",
            "--output-root $RemoteDataRoot/pixie_research/$tag"
        ) -join " "
        Invoke-Remote $cmd
    }
    "prose-exact-train" {
        Sync-Workspace
        $envPrefix = Remote-PixieEnvPrefix
        $tag = Default-Tag -Prefix "pixie_snacksack_prose_exact"
        $cmd = @(
            $envPrefix,
            "python3 $RemoteRoot/run_pixie_storyworld_sft.py",
            "--models 1.7B",
            "--skip-mixed-pass",
            "--skip-action-pass",
            "--skip-prose-pass",
            "--run-prose-exact-pass",
            "--skip-bridge",
            "--pixie-root $RemoteRoot",
            "--merge-env $RemoteRoot/build_pixie_storyworld_sft_env.py",
            "--tesseract-train $RemoteRoot/external/train_qlora.py",
            "--soul-path $RemoteRoot/inputs/soul.md",
            "--constitution-path $RemoteRoot/inputs/fae_constitution_seed.jsonl",
            "--comparison-path $RemoteRoot/inputs/route_ablation_comparison.json",
            "--data-root $RemoteDataRoot",
            "--prose-exact-save-steps 1000",
            "--save-total-limit 1",
            "--output-root $RemoteDataRoot/pixie_research/$tag"
        ) -join " "
        Invoke-Remote $cmd
    }
    "buddy-distill" {
        Sync-Workspace
        $envPrefix = Remote-PixieEnvPrefix
        $cmd = @(
            $envPrefix,
            "python3 $RemoteRoot/generate_reflective_buddy_distill.py",
            "--data-root $RemoteDataRoot",
            "--chat-template chatml",
            "--examples-per-scenario 1",
            "--max-tokens 96",
            "--max-attempts 3",
            "--temperature 0.1",
            "--request-timeout-sec 420",
            "--health-timeout-sec 300",
            "--port 8091",
            "--n-gpu-layers 32"
        ) -join " "
        Invoke-Remote $cmd
    }
    "buddy-fetch" {
        $dateTag = Resolve-BuddyDate
        $remoteResearch = "$RemoteDataRoot/pixie_research"
        $remoteNorm = "$RemoteDataRoot/normalized_trajectories"
        $localResearch = Join-Path $LocalDataRoot "pixie_research"
        $localNorm = Join-Path $LocalDataRoot "normalized_trajectories"

        $copies = @()
        if ($dateTag) {
            $copies += @(
                @{ Remote = "$remoteResearch/reflective_buddy_teacher_${dateTag}.jsonl"; Local = (Join-Path $localResearch "reflective_buddy_teacher_${dateTag}.jsonl"); Required = $false },
                @{ Remote = "$remoteResearch/reflective_buddy_teacher_memory_${dateTag}.jsonl"; Local = (Join-Path $localResearch "reflective_buddy_teacher_memory_${dateTag}.jsonl"); Required = $false },
                @{ Remote = "$remoteResearch/reflective_buddy_teacher_manifest_${dateTag}.json"; Local = (Join-Path $localResearch "reflective_buddy_teacher_manifest_${dateTag}.json"); Required = $false },
                @{ Remote = "$remoteResearch/reflective_buddy_teacher_log_${dateTag}.jsonl"; Local = (Join-Path $localResearch "reflective_buddy_teacher_log_${dateTag}.jsonl"); Required = $false }
            )
        }
        $copies += @(
            @{ Remote = "$remoteResearch/reflective_buddy_distill_runner.log"; Local = (Join-Path $localResearch "reflective_buddy_distill_runner.log"); Required = $true },
            @{ Remote = "$remoteNorm/pixue_reflective_buddy_teacher.jsonl"; Local = (Join-Path $localNorm "pixue_reflective_buddy_teacher.jsonl"); Required = $true }
        )

        foreach ($entry in $copies) {
            $copied = Copy-FromRemoteFileIfExists -RemotePath $entry.Remote -LocalPath $entry.Local
            if (-not $copied -and $entry.Required) {
                throw "Missing required remote file: $($entry.Remote)"
            }
        }
    }
    "full-eval" {
        if (-not $AdapterPath) {
            throw "AdapterPath is required for full-eval."
        }
        Sync-Workspace
        $envPrefix = Remote-PixieEnvPrefix
        $tag = Default-Tag -Prefix "faebench_compare_full"
        $cmd = @(
            $envPrefix,
            "python3 $RemoteRoot/build_faebench_env.py",
            "--output $RemoteDataRoot/normalized_trajectories/faebench.jsonl",
            "--manifest $RemoteDataRoot/pixie_research/faebench_manifest.json",
            "&&",
            $envPrefix,
            "python3 $RemoteRoot/run_faebench_compare.py",
            "--models 1.7B",
            "--bench $RemoteDataRoot/normalized_trajectories/faebench.jsonl",
            "--adapter-path 1.7B=$AdapterPath",
            "--output $RemoteDataRoot/pixie_research/$tag.json"
        ) -join " "
        Invoke-Remote $cmd
    }
}
