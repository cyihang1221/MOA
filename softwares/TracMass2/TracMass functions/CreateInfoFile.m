function CreateInfoFile(CW)

%by: Erik Tengstrand
if ~ischar(CW.SampleList.ProjectPath)
    return
end

Path=CW.SampleList.ProjectPath;
File=[Path filesep 'ProjectInfo.txt'];
outfid = fopen(File,'w+t');

fprintf(outfid,'Project folder: ');
fprintf(outfid,'%s',Path);
fprintf(outfid,'\n\n');

fprintf(outfid,'Samples:');
Samples=CW.SampleList.SamplePath;
fprintf(outfid,'\n');
if ischar(Samples)
    fprintf(outfid,'%s',Samples);
end
if iscell(Samples)
    for N=1:numel(Samples)
        fprintf(outfid,'%s',Samples{N});
        fprintf(outfid,'\n');
    end
end
fprintf(outfid,'\n\n');

fprintf(outfid,'Outliers:');
Outliers=CW.Outliers.SamplePath;
fprintf(outfid,'\n');
if ischar(Outliers)
    fprintf(outfid,'%s',Outliers);
end
if iscell(Outliers)
    for N=1:numel(Outliers)
        fprintf(outfid,'%s',Outliers{N});
        fprintf(outfid,'\n');
    end
end
fclose(outfid);