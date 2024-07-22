#!/bin/bash

print_usage(){
  if [ $# -gt 0 ]; then
      echo "Missing argument ${1}"
  fi
  echo "Usage:"
  echo "$0 -r [github run id] -w [github workflow] -a [github action id] -b [github ref id] -e [Optional extras] -f [ should we fail?] -l [instal, time limit]"
  echo "Extras should be written as it appears in pip, for example for promptflow-evals[azure], it will be [azure]"
  echo "Flag -f does not require parameter."
  exit 1
}

run_id=""
workflow=""
action=""
ref=""
fail=0
extras=""
limit=""


while getopts ":r:w:a:b:e:l:f" opt; do
# Parse options
  case $opt in
    (r) run_id="$OPTARG";;
    (w) workflow="$OPTARG";;
    (a) action="$OPTARG";;
    (b) ref="$OPTARG";;
    (e) extras="$OPTARG";;
    (f) ((fail++));;
    (l) limit="$OPTARG";;
    \?) print_usage;;
  esac
done
  
for v in "run_id" "workflow" "action" "ref" "limit"; do
    if [ -z ${!v} ]; then
        print_usage "$v"
    fi
done

ENV_DIR="test_pf_ev"
python -m virtualenv "${ENV_DIR}"
# Make activate command platform independent
ACTIVATE="${ENV_DIR}/bin/activate"
if [ ! -f "$ACTIVATE" ]; then
  ACTIVATE="${ENV_DIR}/Scripts/activate"
fi
source "${ACTIVATE}"
# Estimate the installation time.
pf_evals_wheel=`ls -1 promptflow_evals-*`
echo "The downloaded wheel file ${pf_evals_wheel}"
packages=`python -m pip freeze | wc -l`
start_tm=`date +%s`
echo "python -m pip install \"./${pf_evals_wheel}${extras}\" --no-cache-dir"
python -m pip install "./${pf_evals_wheel}${extras}" --no-cache-dir
install_time=$((`date +%s` - ${start_tm}))
packages_installed=$((`python -m pip freeze | wc -l` - packages))
# Log the install time
python `dirname "$0"`/report_to_app_insights.py --activity "install_time_s" --value "{\"install_time_s\": ${install_time}, \"number_of_packages_installed\": ${packages_installed}}" --git-hub-action-run-id "${run_id}" --git-hub-workflow "${workflow}" --git-hub-action "${action}" --git-branch "${ref}"
deactivate
rm -rf test_pf_ev
echo "Installed ${packages_installed} packages per ${install_time} seconds."
if [ $fail -eq 0 ]; then
    # Swallow the exit code 1 and just show the warning, understandable by
    # github UI.
    test ${install_time} -le $limit || echo "::warning file=pyproject.toml,line=40,col=0::The installation took ${install_time} seconds, the limit is ${limit}."
else
    test ${install_time} -le $limit
fi
# Return the exit code of test command of of echo i.e. 0.
exit $?