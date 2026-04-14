% run this file to install TracMass

%by: Magnus Åberg
try	

pth = fileparts(which(mfilename));
P = { pth,...
    fullfile(pth,'TracMass functions'),...
    fullfile(pth,'mexnc'),...
    fullfile(pth,'snctools'),...
    fullfile( pth, 'SplashScreen-v1p1' )
    };
    
run( fullfile(pth, [ 'GUILayout-v1p14', filesep, 'install.m' ] ) )
addpath(P{:})
stat = savepath;

assert(stat==0,sprintf('TracMass could not be installed properly\nbecause path could not be saved.\n%s',...
    'To use TracMass, you will have to reinstall it next time Matlab is started.'))
clear stat pth P
catch
    clear stat pth P
    rethrow(lasterror)
end