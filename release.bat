@echo off

:: Verifier si on est sur la branche main
for /f "tokens=*" %%i in ('git branch --show-current') do set CurrentBranch=%%i
if "%CurrentBranch%" NEQ "main" goto ErrorBranch

:: Verifier si le dossier est propre (pas de changements non commités)
git diff-index --quiet HEAD --
if %ERRORLEVEL% NEQ 0 goto ErrorStatus

set /p Version="Entrez la version a deployer (ex: 1.0.2) : "

if "%Version%"=="" goto Error

echo.
set /p Description="Description de la release (optionnel) : "
if "%Description%"=="" set Description=Release v%Version%


echo.
echo ============================================
echo  Deploiement de la version v%Version%
echo ============================================
echo.

git tag -a v%Version% -m "%Description%"
if %ERRORLEVEL% NEQ 0 goto ErrorGit

git push origin v%Version%
if %ERRORLEVEL% NEQ 0 goto ErrorGit

echo.
echo -----------------------------------------------------------
echo  Succes ! La version v%Version% a ete envoyee sur GitHub.
echo  Le .exe sera bientot disponible dans l'onglet 'Releases'.
echo -----------------------------------------------------------
pause
exit

:Error
echo Erreur : Vous devez entrer un numero de version.
pause
exit

:ErrorBranch
echo.
echo ERREUR : Vous devez etre sur la branche 'main' pour deployer.
echo Branche actuelle : %CurrentBranch%
pause
exit

:ErrorStatus
echo.
echo ERREUR : Vous avez des fichiers non versionnes ou modifies.
echo Merci de commit ou stash vos changements avant de deployer.
pause
exit

:ErrorGit
echo.
echo ERREUR : Une erreur Git est survenue.
echo Verifiez que vous n'avez pas deja utilise ce tag.
pause
exit
