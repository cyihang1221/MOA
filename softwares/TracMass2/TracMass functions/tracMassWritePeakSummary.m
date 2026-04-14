function [] = tracMassWritePeakSummary(file,db,transpose,param)

%by: Magnus Åberg

fid = fopen(file,'w+t');
assert( fid > 0, sprintf( 'Error opening file: "%s"\n', file ))

dlm_ = ',';
if ~exist('transpose','var')
    transpose = false;
end
consistencyLimit = 0;
intensityLimit = 0;
if exist('param','var')
    if isfield(param,'consistency')
        consistencyLimit = param.consistency;
    end
    if isfield(param,'intensity')
        intensityLimit = param.intensity;
    end
end


[X,objLabel,varLabel] = tracMassGetPeakSummary(db,transpose,consistencyLimit,intensityLimit);


if ~transpose,
    for i = 1:4,
        fprintf(fid,['%s',dlm_],'',varLabel{:,i});
        if i < 3, fprintfln(fid); end
    end
    for i = 1:size(X,1),
        fprintfln(fid);
        fprintf(fid,['%s',dlm_],objLabel{i});
        fprintf(fid,['%.1f',dlm_],X(i,:));
    end
else
    fprintf(fid,['%s',dlm_],'','m/z','time','binned');
    fprintf(fid,['%s',dlm_],varLabel{:});
    for i = 1:size(X,1),
        fprintfln(fid);
        fprintf(fid,['%s',dlm_],objLabel{i,:});
        fprintf(fid,['%.1f',dlm_],X(i,:));
    end
end
fclose(fid);